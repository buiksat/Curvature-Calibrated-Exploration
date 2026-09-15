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

filegroup(
    name = "realistic_transport_resources",
    srcs = [
        ".buck2",
        ".buckconfig",
        ".buck/fbsource_cell/.buckconfig",
        ".buck/fbsource_cell/arvr",
        ".buck/fbsource_cell/fbandroid",
        ".buck/fbsource_cell/fbcode",
        ".buck/fbsource_cell/fbobjc",
        ".buck/fbsource_cell/genai",
        ".buck/fbsource_cell/nest",
        ".buck/fbsource_cell/opsfiles",
        ".buck/fbsource_cell/ovrsource-legacy",
        ".buck/fbsource_cell/third-party",
        ".buck/fbsource_cell/thrift_sync",
        ".buck/fbsource_cell/tools",
        ".buck/fbsource_cell/users",
        ".buck/fbsource_cell/whatsapp",
        ".buck/fbsource_cell/www",
        ".buck/fbsource_cell/xplat",
        "BUCK",
        "BUCK2_SETUP.md",
        "PACKAGE",
        "pytest.ini",
        "paper/BUCK",
        "paper/validate.py",
        "//experiments/realistic_transport:realistic_transport_package_inventory_resources",
        "//experiments/tests:realistic_transport_experiment_tests_inventory_resources",
        "//experiments:realistic_transport_experiments_inventory_resources",
        "//tests:realistic_transport_root_tests_inventory_resources",
        "//third_party:realistic_transport_third_party_inventory_resources",
        "//tools:realistic_transport_tools_inventory_resources",
    ] + glob([
        ".buck/fbsource_cell/.buckconfig.d/**",
        ".buck/fbsource_cell/.buckconfig.local",
        ".buck/fbsource_cell/.buckroot",
        ".buck2-previous",
        ".buck2-versions/**",
        ".buckconfig.d/**",
        ".buckconfig.local",
        ".buckroot",
        "BUCK_TREE",
        "*.bzl",
        "*.py",
        "*.pyc",
        "*.pyi",
        "*.pyo",
        "*.so",
        "**/*.bzl",
        "**/*.py",
        "**/*.pyc",
        "**/*.pyi",
        "**/*.pyo",
        "**/*.so",
    ], exclude = [
        "buck-out/**",
        "results/logs/**",
        "results/raw/**",
    ]),
    visibility = ["PUBLIC"],
)
