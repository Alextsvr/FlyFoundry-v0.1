# FlyFoundry run FAILED

- Error: `TypeError: Opportunity.__init__() got an unexpected keyword argument 'detail'`
- No experiment state was modified after the error (checkpoints are written atomically).
- Recovery: run `flyfoundry validate --state-dir <dir>`; a missing state is never silently replaced by a fresh start.
