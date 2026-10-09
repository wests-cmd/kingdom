import json
import re
from urllib.request import Request, urlopen
from fastapi import APIRouter, Depends, HTTPException
from backend.security.http_auth import require_owner
from backend.state import STATE
from backend.system.ui_updates import UIComponents

router=APIRouter(prefix='/updates/ui',dependencies=[Depends(require_owner)])


def components(): return UIComponents(STATE['version'])


def candidate():
    request=Request('https://api.github.com/repos/wests-cmd/kingdom/releases/latest',headers={'Accept':'application/vnd.github+json','User-Agent':'Kingdom-component-update'})
    with urlopen(request,timeout=10) as response: release=json.loads(response.read(1024*1024))
    tag=release.get('tag_name','')
    if release.get('draft') or release.get('prerelease') or not re.fullmatch(r'v\d+\.\d+\.\d+',tag): raise ValueError('No stable release available')
    name=f'Kingdom-UI-{tag[1:]}.zip'
    asset=next((asset for asset in release.get('assets',[]) if asset['name']==name),None)
    if not asset: return {'available':False,'release_url':release['html_url'],'reason':'This release requires its native installer; no UI-only package is published.'}
    digest=asset.get('digest','')
    if not re.fullmatch('sha256:[a-f0-9]{64}',digest) or not 0<asset.get('size',0)<=8*1024*1024: raise ValueError('Published package has no trusted checksum or exceeds limits')
    return {'available':True,'sha256':digest[7:],'tag':tag,'name':name,'release_url':release['html_url'],
            'download_url':f'https://github.com/wests-cmd/kingdom/releases/download/{tag}/{name}'}


@router.get('')
def status(): return components().status()


@router.get('/check')
def check():
    try: return candidate()
    except Exception as error: raise HTTPException(502,'Could not verify a published UI update') from error


@router.post('/apply')
def apply():
    try:
        update=candidate()
        if not update['available']: raise ValueError(update['reason'])
        with urlopen(update['download_url'],timeout=30) as response: data=response.read(8*1024*1024+1)
        result=components().install(data,update['sha256'])
        from backend.api import engine
        engine.events.publish('update.ui_activated',{'sha256':update['sha256']})
        return result
    except ValueError as error: raise HTTPException(409,str(error)) from error
    except Exception as error: raise HTTPException(502,'UI update failed; the current component remains selected') from error


@router.post('/rollback')
def rollback():
    try:
        result=components().rollback()
        from backend.api import engine
        engine.events.publish('update.ui_rolled_back',{'active':result['active']})
        return result
    except ValueError as error: raise HTTPException(409,str(error)) from error
