"""Fail-closed Android publisher identity check across apksigner output formats."""
import argparse,os,re,subprocess

def verify_identity(output,expected):
    expected=re.sub(r'[:\s]','',expected).lower()
    if not re.fullmatch(r'[0-9a-f]{64}',expected):raise ValueError('Invalid pinned certificate fingerprint')
    actual=set(value.lower() for value in re.findall(r'^(?:V[1-4] )?Signer[^\n]*certificate SHA-256 digest:\s*([0-9a-fA-F]{64})\s*$',output,re.MULTILINE))
    if actual!={expected}:raise ValueError('APK publisher certificate does not match the pinned identity')
    return expected

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('apksigner');p.add_argument('apk');a=p.parse_args()
    result=subprocess.run([a.apksigner,'verify','--print-certs',a.apk],capture_output=True,text=True,check=True)
    # Signing certificate information is public; private keystore material is never printed.
    print(result.stdout)
    print('Verified publisher SHA-256:',verify_identity(result.stdout,os.environ.get('ANDROID_EXPECTED_CERT_SHA256','')))
