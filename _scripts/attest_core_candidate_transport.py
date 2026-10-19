"""Recompute the existing preparation and attest its exact combined transport bytes."""
import argparse
import json
from pathlib import Path

from _scripts.core_selection_bundle import build, digest, save


def attest(admission_root, generator_root, bundle):
    # build re-reads admitted sources and checks existing prepared frames exactly;
    # it cannot adopt a changed parquet merely by recording its new hash.
    build(admission_root, generator_root, bundle)
    bundle = Path(bundle)
    body = dict(schema='financial_data.candidate_transport_verification.v1', state='VERIFIED',
                prepared_candidates_sha256=digest(bundle/'candidates_train_validation.parquet'),
                train_bundle_sha256=digest(bundle/'REBUILD_INPUT.json'),
                preparation_binding_sha256=digest(bundle/'BINDING.json'),
                verifier_sha256=digest(__file__), checks='RECOMPUTED_SOURCE_RECIPE_AND_EXACT_FRAME_EQUALITY',
                full_inventory_complete=False)
    save(bundle/'TRANSPORT_VERIFICATION.json', body)
    return body


if __name__ == '__main__':
    p = argparse.ArgumentParser(__doc__)
    p.add_argument('--admission-root', type=Path, required=True)
    p.add_argument('--generator-root', type=Path, required=True)
    p.add_argument('--bundle', type=Path, required=True)
    a = p.parse_args()
    print(json.dumps(attest(a.admission_root, a.generator_root, a.bundle), indent=2))
