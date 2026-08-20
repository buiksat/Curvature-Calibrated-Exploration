load(
    "@fbcode//buck2/platform/execution:defs.bzl",
    "execution_platform",
    "execution_platforms",
)

local_platforms = execution_platform(
    name = "linux_x86_64_local",
    base_platform = "fbcode//buck2/platform/execution:platform010",
    local_enabled = True,
    make_dash_only_platforms = False,
    remote_enabled = False,
    remote_execution_max_input_files_mebibytes = 512 * 1024,
)

execution_platforms(
    name = "local_execution_platforms",
    fallback = "error",
    platforms = local_platforms,
)

filegroup(
    name = "repository_resources",
    srcs = glob([
        "*.md",
        "paper/**",
        "results/derived/**",
        # Detached GitHub-auditability tooling and its committed review bundle.
        # Listed so that editing either retriggers the test targets that read
        # them from the project root.
        "tools/*.py",
        "review/**",
    ]),
    visibility = ["PUBLIC"],
)
