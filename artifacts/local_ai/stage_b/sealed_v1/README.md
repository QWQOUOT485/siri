# Stage B held-out seal v1

`held_out.jsonl` is a byte-identical, write-once snapshot of the frozen
`final_v1/held_out.jsonl`. Its labels are evaluation-only. They are unavailable
to training, fine-tuning, checkpoint or model selection, calibration, threshold
fitting, prompts, and augmentation. This seal grants no evaluation/model compute
authorization; that requires a separate reviewed gate.

The repository-owned seal command creates this directory only when absent.
Thereafter use `--verify` to check source and sealed identities without writes.
Any mismatch or unexpected file fails closed. Git and filesystem read-only bits
alone are not the integrity boundary. The historical `final_v1` manifests keep
their original `held_out_sealed=false` state; only `seal_manifest.json` records
completion of this seal step.
