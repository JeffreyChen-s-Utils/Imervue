# Interpreter probe next-stage assessment

The captured stack proves blocking in Windows process creation, reached through _verify_python and subprocess.run. It does not establish an OS dialog, security product or other native cause. The deterministic ENOEXEC unit test verifies application error handling; it does not certify native creation rejection or repair a stalled production probe.

The subprocess timeout starts after process creation. A thread/future timeout cannot cancel a blocked creation and can leave a late child or lingering thread. Existing terminate_process requires an acquired Popen and includes a final unbounded wait. PE prechecks or thread error-mode flags may be investigated but cannot establish a complete deadline and have compatibility/race or unproven-cause limitations.

A ready helper in a Windows Job Object is a candidate for bounding candidate probes. Assign the helper to a kill-on-close job before it can receive a candidate, prohibit breakaway, require READY, and close/terminate the whole job on deadline to own descendants even before their PIDs are returned. The helper bootstrap still calls CreateProcess and has no absolute in-process deadline; never describe this as a hard bound on cold-start discovery without an already-running external supervisor.

Frozen packaging needs an early helper entry before GUI/OpenGL startup and explicit IPC; the windowed PyInstaller executable cannot be treated as ordinary Python accepting -c. Preserve the _verify_python bool/error contract, finder order and pip_installer compatibility exports. Installer finder/download workers are already background operations, but object_splitter._get_frozen_env is called synchronously from its ready callback before the dialog executes; all GUI call sites need a separate threading audit. Plugin changes must follow distribution parity rules.

Future verification should cover pre-child hangs injected inside the helper, late-child races, descendant cleanup, READY/job assignment failures, IPC EOF/corruption, concurrent probes, parent exit and repeated handle/process counts. Preserve real valid-Python probes and search-order tests. Verify a frozen build without visible GUI/console or recursive GUI startup. Do not reproduce by launching another arbitrary invalid executable on the user's desktop.

This was a read-only assessment. No production solution or hard-deadline guarantee has been implemented. References: Python subprocess documentation and Microsoft Job Objects documentation; the captured local stack is .audit/third-cohort-hang-stack.txt.
