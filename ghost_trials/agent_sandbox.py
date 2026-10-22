"""Child-process bootstrap for bundled reference agents.

Limits are applied by the child itself, so the parent never runs code between fork and exec
(subprocess preexec_fn is unsafe from the API's worker threads). This bounds resources only; it is
not a filesystem or network sandbox and must not be used for third-party code.
"""
import resource
import runpy

LIMITS = {
    resource.RLIMIT_CPU: 2,
    resource.RLIMIT_AS: 256 * 1024 * 1024,
    resource.RLIMIT_FSIZE: 0,
    resource.RLIMIT_NOFILE: 16,
}


def apply_limits():
    for kind, value in LIMITS.items():
        resource.setrlimit(kind, (value, value))


if __name__ == "__main__":
    apply_limits()
    runpy.run_module("ghost_trials.agent_reference", run_name="__main__", alter_sys=True)
