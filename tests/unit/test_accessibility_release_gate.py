from copy import deepcopy
import pytest
from scripts.release_artifacts import verify_accessibility_evidence


PROOF={
    'appearance':{'logoLoaded':True,'lightModeApplied':True,'persistedAfterReload':True,'resetVerified':True},
    'accessibility':{'highContrastApplied':True,'scale200Applied':True,'noHorizontalOverflow':True,'ownerPreferencesSaved':True,'persistedAfterReload':True},
}


def test_release_rejects_missing_failed_or_string_accessibility_proof():
    verify_accessibility_evidence(PROOF,'1.1.2')
    for field in PROOF['accessibility']:
        for wrong in [False,None,'true']:
            evidence=deepcopy(PROOF)
            evidence['accessibility'][field]=wrong
            with pytest.raises(RuntimeError):
                verify_accessibility_evidence(evidence,'1.1.2')
    with pytest.raises(RuntimeError):
        verify_accessibility_evidence({},'1.1.2')


def test_older_release_can_be_verified_without_new_feature_claims():
    verify_accessibility_evidence({},'1.1.1')
    with pytest.raises(ValueError):
        verify_accessibility_evidence(PROOF,'invalid')
