import io
import wave
import pytest
from backend.runtime import local_transcription as voice


def wav(rate=16000,channels=1,frames=160):
    data=io.BytesIO()
    with wave.open(data,'wb') as out:
        out.setnchannels(channels);out.setsampwidth(2);out.setframerate(rate)
        out.writeframes(b'\x00'*(frames*channels*2))
    return data.getvalue()


@pytest.mark.parametrize('data',[b'not audio',wav(rate=8000),wav(channels=2),wav(frames=0),wav()[:-2]])
def test_reject_invalid_audio(data):
    with pytest.raises(ValueError):voice.validate_wav(data)


def test_missing_local_model_never_launches_process(monkeypatch):
    monkeypatch.delenv('KINGDOM_WHISPER_CLI',raising=False)
    monkeypatch.delenv('KINGDOM_WHISPER_MODEL',raising=False)
    monkeypatch.setattr(voice.subprocess,'run',lambda *a,**kw:pytest.fail('Unexpected process'))
    with pytest.raises(RuntimeError):voice.transcribe(wav())


def test_adapter_uses_only_configured_local_executable_and_cleans_input(tmp_path,monkeypatch):
    binary=tmp_path/'whisper-cli';binary.touch()
    model=tmp_path/'model.bin';model.touch()
    monkeypatch.setenv('KINGDOM_WHISPER_CLI',str(binary))
    monkeypatch.setenv('KINGDOM_WHISPER_MODEL',str(model))
    monkeypatch.setenv('OPENAI_API_KEY','never-pass-to-child')
    seen={}
    def launch(argv,**kwargs):
        from pathlib import Path
        seen.update(kwargs)
        assert argv[0]==str(binary) and argv[2]==str(model)
        assert kwargs['shell'] is False and kwargs['timeout']==120
        assert 'OPENAI_API_KEY' not in kwargs['env']
        source=Path(argv[argv.index('-f')+1])
        assert source.read_bytes()==wav()
        Path(argv[argv.index('-of')+1]+'.txt').write_text('review this transcript')
    monkeypatch.setattr(voice.subprocess,'run',launch)
    result=voice.transcribe(wav())
    assert result['text']=='review this transcript' and result['requires_review']
    assert not seen['cwd'].exists()
