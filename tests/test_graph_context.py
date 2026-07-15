import errno
import stat
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from projectpilot import graph_context


_SYMLINK_SKIP_ERRNOS = frozenset(
    value
    for name in ("EPERM", "EACCES", "ENOSYS", "EOPNOTSUPP", "ENOTSUP")
    if (value := getattr(errno, name, None)) is not None
)


def write_config(base: Path, text: str) -> None:
    config_dir = base / ".project-pilot"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "config.yaml").write_text(text, encoding="utf-8")


def write_outputs(base: Path, *, graph: bool, report: bool, output_dir="graphify-out") -> None:
    out = base / output_dir
    out.mkdir(parents=True, exist_ok=True)
    if graph:
        (out / "graph.json").write_text("{}\n", encoding="utf-8")
    if report:
        (out / "GRAPH_REPORT.md").write_text("# Report\n", encoding="utf-8")


def symlink_or_skip(
    test: unittest.TestCase,
    link: Path,
    target: Path,
    *,
    target_is_directory: bool = False,
) -> None:
    try:
        link.symlink_to(target, target_is_directory=target_is_directory)
    except NotImplementedError as exc:
        test.skipTest(f"platform does not permit creating this symlink: {exc}")
    except OSError as exc:
        if exc.errno in _SYMLINK_SKIP_ERRNOS or getattr(exc, "winerror", None) == 1314:
            test.skipTest(f"platform does not permit creating this symlink: {exc}")
        raise


class InspectGraphContextTests(unittest.TestCase):
    def test_unconfigured_is_disabled_with_stable_defaults(self):
        with tempfile.TemporaryDirectory() as d:
            status = graph_context.inspect_graph_context(Path(d))
            self.assertFalse(status.enabled)
            self.assertEqual(status.state, graph_context.STATE_DISABLED)
            self.assertEqual(status.graph_path, "graphify-out/graph.json")
            self.assertEqual(status.report_path, "graphify-out/GRAPH_REPORT.md")
            self.assertEqual(status.query_budget, 1200)
            self.assertEqual(status.diagnostics, ())
            self.assertFalse(status.output_path_usable)

    def test_unconfigured_disabled_status_does_not_resolve_paths(self):
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.object(
                Path,
                "resolve",
                side_effect=AssertionError("disabled mode resolved a path"),
            ):
                status = graph_context.inspect_graph_context(Path(d))

            self.assertFalse(status.enabled)
            self.assertEqual(status.state, graph_context.STATE_DISABLED)
            self.assertEqual(status.graph_path, "graphify-out/graph.json")
            self.assertEqual(status.report_path, "graphify-out/GRAPH_REPORT.md")
            self.assertEqual(status.query_budget, 1200)
            self.assertEqual(status.diagnostics, ())

    def test_explicit_false_uses_stable_defaults_without_resolving_paths(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            write_config(
                base,
                "graphify_enabled: false\n"
                "graphify_output_dir: ../outside\n"
                "graphify_query_budget: invalid\n",
            )
            with mock.patch.object(
                Path,
                "resolve",
                side_effect=AssertionError("disabled mode resolved a path"),
            ):
                status = graph_context.inspect_graph_context(base)

            self.assertFalse(status.enabled)
            self.assertEqual(status.state, graph_context.STATE_DISABLED)
            self.assertEqual(status.graph_path, "graphify-out/graph.json")
            self.assertEqual(status.report_path, "graphify-out/GRAPH_REPORT.md")
            self.assertEqual(status.query_budget, 1200)
            self.assertEqual(status.diagnostics, ())
            self.assertFalse(status.output_path_usable)

    def test_enabled_states_are_missing_partial_and_ready(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            write_config(base, "graphify_enabled: true\n")
            missing_status = graph_context.inspect_graph_context(base)
            self.assertEqual(missing_status.state, graph_context.STATE_MISSING)
            self.assertTrue(missing_status.output_path_usable)
            write_outputs(base, graph=True, report=False)
            self.assertEqual(
                graph_context.inspect_graph_context(base).state,
                graph_context.STATE_PARTIAL,
            )
            write_outputs(base, graph=True, report=True)
            self.assertEqual(
                graph_context.inspect_graph_context(base).state,
                graph_context.STATE_READY,
            )

    def test_custom_safe_output_and_budget_are_preserved(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            write_config(
                base,
                "graphify_enabled: yes\n"
                "graphify_output_dir: .context/graphify\n"
                "graphify_query_budget: 2500\n",
            )
            write_outputs(base, graph=True, report=True, output_dir=".context/graphify")
            status = graph_context.inspect_graph_context(base)
            self.assertTrue(status.enabled)
            self.assertEqual(status.state, graph_context.STATE_READY)
            self.assertEqual(status.graph_path, ".context/graphify/graph.json")
            self.assertEqual(status.report_path, ".context/graphify/GRAPH_REPORT.md")
            self.assertEqual(status.query_budget, 2500)
            self.assertTrue(status.output_path_usable)

    def test_escape_and_invalid_values_fall_back_with_diagnostics(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            write_config(
                base,
                "graphify_enabled: perhaps\n"
                "graphify_output_dir: ../outside\n"
                "graphify_query_budget: many\n",
            )
            original_lstat = Path.lstat

            def forbid_output_lstat(path):
                if path.name in {"graph.json", "GRAPH_REPORT.md"}:
                    raise AssertionError("invalid boolean probed output metadata")
                return original_lstat(path)

            with mock.patch.object(Path, "lstat", new=forbid_output_lstat):
                status = graph_context.inspect_graph_context(base)
            self.assertFalse(status.enabled)
            self.assertEqual(status.state, graph_context.STATE_DISABLED)
            self.assertEqual(status.graph_path, "graphify-out/graph.json")
            self.assertEqual(status.query_budget, 1200)
            self.assertEqual(
                status.diagnostics,
                (
                    "graphify_enabled is invalid; using false.",
                    "graphify_output_dir must stay inside the project; using graphify-out.",
                    "graphify_query_budget must be an integer from 250 through 5000; using 1200.",
                ),
            )

    def test_budget_boundaries_are_inclusive(self):
        for budget in (250, 5000):
            with self.subTest(budget=budget), tempfile.TemporaryDirectory() as d:
                base = Path(d)
                write_config(
                    base,
                    f"graphify_enabled: true\ngraphify_query_budget: {budget}\n",
                )
                self.assertEqual(
                    graph_context.inspect_graph_context(base).query_budget,
                    budget,
                )

    def test_embedded_nul_output_dir_falls_back_without_crashing(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            write_config(
                base,
                "graphify_enabled: true\ngraphify_output_dir: bad\x00path\n",
            )

            status = graph_context.inspect_graph_context(base)

            self.assertTrue(status.enabled)
            self.assertEqual(status.state, graph_context.STATE_MISSING)
            self.assertEqual(status.graph_path, "graphify-out/graph.json")
            self.assertEqual(status.report_path, "graphify-out/GRAPH_REPORT.md")
            self.assertTrue(status.output_path_usable)
            self.assertEqual(
                status.diagnostics,
                ("graphify_output_dir cannot be resolved; using graphify-out.",),
            )

    def test_unsafe_linked_fallback_directory_is_not_probed(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            base = root / "project"
            outside = root / "outside"
            base.mkdir()
            outside.mkdir()
            write_config(
                base,
                "graphify_enabled: true\ngraphify_output_dir: ../configured-escape\n",
            )
            write_outputs(outside, graph=True, report=True, output_dir=".")
            symlink_or_skip(
                self,
                base / graph_context.DEFAULT_OUTPUT_DIR,
                outside,
                target_is_directory=True,
            )

            status = graph_context.inspect_graph_context(base)

            self.assertEqual(status.state, graph_context.STATE_MISSING)
            self.assertEqual(status.graph_path, "graphify-out/graph.json")
            self.assertEqual(status.report_path, "graphify-out/GRAPH_REPORT.md")
            self.assertFalse(status.output_path_usable)
            self.assertEqual(
                status.diagnostics,
                (
                    "graphify_output_dir must stay inside the project; using graphify-out.",
                    "default graphify-out directory must stay inside the project; "
                    "outputs will not be inspected.",
                ),
            )

    def test_unresolvable_fallback_directory_is_not_probed(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            write_config(
                base,
                "graphify_enabled: true\ngraphify_output_dir: ../configured-escape\n",
            )
            original_resolve = Path.resolve

            def fail_default(path, *args, **kwargs):
                if path.name == graph_context.DEFAULT_OUTPUT_DIR:
                    raise OSError("unresolvable fallback")
                return original_resolve(path, *args, **kwargs)

            with mock.patch.object(Path, "resolve", new=fail_default):
                status = graph_context.inspect_graph_context(base)

            self.assertEqual(status.state, graph_context.STATE_MISSING)
            self.assertFalse(status.output_path_usable)
            self.assertEqual(
                status.diagnostics,
                (
                    "graphify_output_dir must stay inside the project; using graphify-out.",
                    "default graphify-out directory cannot be resolved; "
                    "outputs will not be inspected.",
                ),
            )

    def test_linked_output_files_are_not_counted_as_regular_outputs(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            base = root / "project"
            outside = root / "outside"
            base.mkdir()
            outside.mkdir()
            write_config(base, "graphify_enabled: true\n")
            output_dir = base / graph_context.DEFAULT_OUTPUT_DIR
            output_dir.mkdir()
            (outside / "graph.json").write_text("{}\n", encoding="utf-8")
            (outside / "GRAPH_REPORT.md").write_text("# Report\n", encoding="utf-8")
            symlink_or_skip(self, output_dir / "graph.json", outside / "graph.json")
            symlink_or_skip(
                self,
                output_dir / "GRAPH_REPORT.md",
                outside / "GRAPH_REPORT.md",
            )

            status = graph_context.inspect_graph_context(base)

            self.assertEqual(status.state, graph_context.STATE_MISSING)
            self.assertEqual(
                status.diagnostics,
                (
                    "Graphify graph output is not a safe regular file; "
                    "treating it as missing.",
                    "Graphify report output is not a safe regular file; "
                    "treating it as missing.",
                ),
            )

    def test_windows_reparse_point_outputs_are_not_counted_as_regular_files(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            write_config(base, "graphify_enabled: true\n")
            write_outputs(base, graph=True, report=True)
            original_lstat = Path.lstat
            reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
            reparse_metadata = SimpleNamespace(
                st_mode=stat.S_IFREG,
                st_file_attributes=reparse_flag,
            )

            def mark_outputs_as_reparse_points(path):
                if path.name in {"graph.json", "GRAPH_REPORT.md"}:
                    return reparse_metadata
                return original_lstat(path)

            with mock.patch.object(
                Path,
                "lstat",
                new=mark_outputs_as_reparse_points,
            ):
                status = graph_context.inspect_graph_context(base)

            self.assertEqual(status.state, graph_context.STATE_MISSING)
            self.assertFalse(status.output_path_usable)
            self.assertEqual(
                status.diagnostics,
                (
                    "Graphify graph output is not a safe regular file; "
                    "treating it as missing.",
                    "Graphify report output is not a safe regular file; "
                    "treating it as missing.",
                ),
            )

    def test_output_metadata_errors_fail_soft(self):
        for error_type in (ValueError, OSError, RuntimeError):
            with self.subTest(error_type=error_type), tempfile.TemporaryDirectory() as d:
                base = Path(d)
                write_config(base, "graphify_enabled: true\n")
                original_is_file = Path.is_file
                original_lstat = Path.lstat

                def fail_output_is_file(path):
                    if path.name in {"graph.json", "GRAPH_REPORT.md"}:
                        raise error_type("metadata unavailable")
                    return original_is_file(path)

                def fail_output_lstat(path):
                    if path.name in {"graph.json", "GRAPH_REPORT.md"}:
                        raise error_type("metadata unavailable")
                    return original_lstat(path)

                with (
                    mock.patch.object(Path, "is_file", new=fail_output_is_file),
                    mock.patch.object(Path, "lstat", new=fail_output_lstat),
                ):
                    status = graph_context.inspect_graph_context(base)

                self.assertEqual(status.state, graph_context.STATE_MISSING)
                self.assertFalse(status.output_path_usable)
                self.assertEqual(
                    status.diagnostics,
                    (
                        "Graphify graph output could not be inspected; "
                        "treating it as missing.",
                        "Graphify report output could not be inspected; "
                        "treating it as missing.",
                    ),
                )

    def test_post_lstat_missing_during_strict_resolution_is_unsafe(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            write_config(base, "graphify_enabled: true\n")
            write_outputs(base, graph=True, report=False)
            original_resolve = Path.resolve

            def fail_graph_strict_resolution(path, *args, **kwargs):
                if path.name == "graph.json" and kwargs.get("strict") is True:
                    raise FileNotFoundError("graph disappeared after metadata inspection")
                return original_resolve(path, *args, **kwargs)

            with mock.patch.object(
                Path,
                "resolve",
                new=fail_graph_strict_resolution,
            ):
                status = graph_context.inspect_graph_context(base)

            self.assertEqual(status.state, graph_context.STATE_MISSING)
            self.assertFalse(status.output_path_usable)
            self.assertEqual(
                status.diagnostics,
                (
                    "Graphify graph output could not be inspected; "
                    "treating it as missing.",
                ),
            )

    def test_post_lstat_resolved_containment_rejection_is_unsafe(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            base = root / "project"
            base.mkdir()
            write_config(base, "graphify_enabled: true\n")
            write_outputs(base, graph=True, report=False)
            outside_graph = root / "outside" / "graph.json"
            outside_graph.parent.mkdir()
            outside_graph.write_text("{}\n", encoding="utf-8")
            outside_graph = outside_graph.resolve()
            original_resolve = Path.resolve

            def escape_graph_strict_resolution(path, *args, **kwargs):
                if path.name == "graph.json" and kwargs.get("strict") is True:
                    return outside_graph
                return original_resolve(path, *args, **kwargs)

            with mock.patch.object(
                Path,
                "resolve",
                new=escape_graph_strict_resolution,
            ):
                status = graph_context.inspect_graph_context(base)

            self.assertEqual(status.state, graph_context.STATE_MISSING)
            self.assertFalse(status.output_path_usable)
            self.assertEqual(
                status.diagnostics,
                (
                    "Graphify graph output could not be inspected; "
                    "treating it as missing.",
                ),
            )

    def test_disabled_mode_does_not_probe_output_metadata(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            write_config(base, "graphify_enabled: false\n")
            original_is_file = Path.is_file
            original_lstat = Path.lstat

            def forbid_output_is_file(path):
                if path.name in {"graph.json", "GRAPH_REPORT.md"}:
                    raise AssertionError("disabled mode probed output metadata")
                return original_is_file(path)

            def forbid_output_lstat(path):
                if path.name in {"graph.json", "GRAPH_REPORT.md"}:
                    raise AssertionError("disabled mode probed output metadata")
                return original_lstat(path)

            with (
                mock.patch.object(Path, "is_file", new=forbid_output_is_file),
                mock.patch.object(Path, "lstat", new=forbid_output_lstat),
            ):
                status = graph_context.inspect_graph_context(base)

            self.assertEqual(status.state, graph_context.STATE_DISABLED)


class RenderQueryDirectiveTests(unittest.TestCase):
    def ready_status(self) -> graph_context.GraphContextStatus:
        return graph_context.GraphContextStatus(
            enabled=True,
            state=graph_context.STATE_READY,
            graph_path="graphify-out/graph.json",
            report_path="graphify-out/GRAPH_REPORT.md",
            query_budget=1200,
        )

    def test_legacy_constructor_defaults_output_path_to_usable(self):
        status = graph_context.GraphContextStatus(
            True,
            graph_context.STATE_READY,
            "graphify-out/graph.json",
            "graphify-out/GRAPH_REPORT.md",
            1200,
            (),
        )

        self.assertTrue(status.output_path_usable)

    def test_non_ready_status_renders_nothing(self):
        status = self.ready_status()
        status = graph_context.GraphContextStatus(
            enabled=status.enabled,
            state=graph_context.STATE_PARTIAL,
            graph_path=status.graph_path,
            report_path=status.report_path,
            query_budget=status.query_budget,
        )
        self.assertEqual(graph_context.render_query_directive(status, "Create PRD"), "")

    def test_ready_status_renders_budgeted_safe_compact_query(self):
        status = self.ready_status()
        first = graph_context.render_query_directive(
            status,
            'Create "PRD"\nwith `evidence`',
        )
        second = graph_context.render_query_directive(
            status,
            'Create "PRD"\nwith `evidence`',
        )
        self.assertEqual(first, second)
        self.assertIn(
            'graphify query "What project context is relevant to Create PRD with evidence?" --budget 1200',
            first,
        )
        self.assertIn("Treat INFERRED or AMBIGUOUS edges as hypotheses.", first)
        self.assertLess(len(first.split()), 100)

    def test_shell_active_skill_name_characters_are_replaced_with_spaces(self):
        rendered = graph_context.render_query_directive(
            self.ready_status(),
            'Deploy $(whoami) ${HOME} %PATH% "quoted" `id` ; rm -rf / '
            "&& echo bad | more > out < in",
        )
        command_line = rendered.splitlines()[1]

        self.assertEqual(
            command_line,
            '`graphify query "What project context is relevant to Deploy whoami HOME '
            'PATH quoted id rm -rf / echo bad more out in?" --budget 1200`',
        )
        for dangerous in ("$(", "${", "%PATH%", '"quoted"', "`id`", ";", "&&", "|", ">", "<"):
            with self.subTest(dangerous=dangerous):
                self.assertNotIn(dangerous, command_line)

    def test_normal_skill_name_allowlist_renders_deterministically(self):
        rendered = graph_context.render_query_directive(
            self.ready_status(),
            "Plan user's API_v2.1 / rollout",
        )

        self.assertIn(
            'graphify query "What project context is relevant to Plan user\'s '
            'API_v2.1 / rollout?" --budget 1200',
            rendered,
        )


if __name__ == "__main__":
    unittest.main()
