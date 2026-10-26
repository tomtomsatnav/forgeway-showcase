"""Command-line entrypoint: ``forgeway content validate | test | new | review | probe``,
``forgeway accounts …`` and ``forgeway waitlist export``."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer

from lattice.application import accounts, plans, rate_limits
from lattice.application.content_check import SOLUTION_BUDGET_S, check_exercise
from lattice.application.content_probe import ProbeBase, probe_exercise
from lattice.application.content_review import ReviewInput, ReviewItem, Status, review_exercise
from lattice.application.content_scaffold import ScaffoldError, scaffold_exercise
from lattice.application.content_sync import current_revision_ids, sync_content
from lattice.application.demo import DEMO_EMAIL, DEMO_PASSWORD, seed_demo_learner
from lattice.application.errors import NotFoundError
from lattice.domain.content import ContentError, PrerequisiteGraph, Tier
from lattice.domain.entitlements import Plan
from lattice.domain.grading import GradeStatus
from lattice.infrastructure.content_loader import ContentCatalogue, load_catalogue, read_tree
from lattice.infrastructure.db.engine import get_engine, session_factory, transaction
from lattice.infrastructure.sandbox_docker import DockerSandboxConfig, DockerSandboxRunner
from lattice.infrastructure.theme_flavour import load_flavour
from lattice.settings import get_settings

app = typer.Typer(no_args_is_help=True, help="Forgeway platform tooling.")
content_app = typer.Typer(no_args_is_help=True, help="Validate and test exercise content.")
app.add_typer(content_app, name="content")
accounts_app = typer.Typer(no_args_is_help=True, help="Account housekeeping.")
app.add_typer(accounts_app, name="accounts")
waitlist_app = typer.Typer(no_args_is_help=True, help="The Forgeway Pro waitlist.")
app.add_typer(waitlist_app, name="waitlist")

ContentDir = Annotated[Path | None, typer.Option(help="Content directory (default: settings).")]


def _load(content_dir: Path | None) -> ContentCatalogue:
    path = content_dir or get_settings().content_dir
    try:
        return load_catalogue(path)
    except ContentError as err:
        for problem in err.problems:
            typer.secho(f"✗ {problem}", fg="red", err=True)
        raise typer.Exit(1) from err


@app.command()
def openapi(output: Annotated[Path, typer.Option(help="Where to write the schema.")]) -> None:
    """Export the API's OpenAPI schema (the frontend client is generated from it)."""
    from lattice.api.app import create_app

    schema = create_app().openapi()
    output.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n")
    typer.secho(f"✓ wrote {output}", fg="green")


@app.command("seed-demo")
def seed_demo(
    passed: Annotated[
        int, typer.Option(help="How many exercises the demo learner has passed.")
    ] = 14,
) -> None:
    """Create a demo learner (demo@forgeway.dev) with partial progress. Local use only."""
    catalogue = _load(None)
    with transaction(session_factory(get_engine())) as session:
        created = seed_demo_learner(
            session,
            catalogue,
            current_revision_ids(session),
            passed,
            free_per_branch=get_settings().free_exercises_per_branch,
        )
    message = f"✓ demo learner ready: {DEMO_EMAIL} / {DEMO_PASSWORD}"
    typer.secho(message if created else f"✓ {DEMO_EMAIL} already exists", fg="green")


@accounts_app.command("purge-unverified")
def purge_unverified() -> None:
    """Delete accounts left unverified for 7 days, expired email tokens and old rate-limit hits.

    Idempotent; run daily (a systemd timer or cron)."""
    with transaction(session_factory(get_engine())) as session:
        summary = accounts.purge_unverified(session)
        hits = rate_limits.prune(session)
    typer.secho(
        f"✓ purged {summary.accounts} unverified account(s), {summary.tokens} expired token(s), "
        f"{hits} old rate-limit hit(s)",
        fg="green",
    )


@accounts_app.command("set-plan")
def set_plan(
    email: Annotated[str, typer.Argument(help="The account's email address.")],
    plan: Annotated[Plan, typer.Argument(help="The plan to put it on.")],
) -> None:
    """Put an account on a plan. There is no billing yet, so this is how Pro is granted."""
    try:
        with transaction(session_factory(get_engine())) as session:
            plans.set_plan(session, email, plan)
    except NotFoundError as err:
        typer.secho(f"✗ {err.detail}", fg="red", err=True)
        raise typer.Exit(1) from err
    typer.secho(f"✓ {email} is on the {plan.value} plan", fg="green")


@waitlist_app.command("export")
def export_waitlist() -> None:
    """Write the waitlist to stdout as CSV (email, plan_interest, joined_at), oldest first."""
    with transaction(session_factory(get_engine())) as session:
        typer.echo(plans.export_waitlist_csv(session), nl=False)


@content_app.command()
def validate(
    content_dir: ContentDir = None,
    require_capstones: Annotated[
        bool,
        typer.Option(
            help="Fail if a branch that requires another has no capstone, or a capstone has no"
            " RPG boss."
        ),
    ] = False,
) -> None:
    """Check content structure, schema and the prerequisite graph without running code."""
    catalogue = _load(content_dir)
    try:
        # CI passes --require-capstones for the shipped content; small trees need none.
        PrerequisiteGraph(
            catalogue.graph.branches.values(),
            catalogue.graph.exercises.values(),
            require_capstones=require_capstones,
        )
    except ContentError as err:
        typer.secho(f"✗ {err}", fg="red", err=True)
        raise typer.Exit(1) from err
    try:
        load_flavour(
            content_dir or get_settings().content_dir,
            "rpg",
            catalogue.graph,
            catalogue.progression.tree.path_ids,
            require_bosses=require_capstones,
        )
    except (ContentError, ValueError) as err:
        typer.secho(f"✗ RPG flavour: {err}", fg="red", err=True)
        raise typer.Exit(1) from err
    typer.secho(
        f"✓ {len(catalogue.graph.branches)} branches, {len(catalogue.sources)} exercises, "
        f"{len(catalogue.progression.tree.nodes)} talents, {len(catalogue.progression.badges)} "
        f"badges, {len(catalogue.releases)} release note(s) valid",
        fg="green",
    )


@content_app.command()
def sync(content_dir: ContentDir = None) -> None:
    """Record the current content in the database (idempotent; run on every deploy)."""
    catalogue = _load(content_dir)
    sessions = session_factory(get_engine())
    with transaction(sessions) as session:
        summary = sync_content(session, catalogue.graph)
    typer.secho(
        f"✓ synced: {summary.new_revisions} new revision(s), {summary.retired} retired",
        fg="green",
    )


@content_app.command("test")
def test_content(
    content_dir: ContentDir = None,
    only: Annotated[
        str | None, typer.Option(help="Only exercises whose id starts with this.")
    ] = None,
    show_time: Annotated[
        bool,
        typer.Option(
            "--time",
            help=f"Print each case's wall-clock time, and flag a solution over "
            f"{SOLUTION_BUDGET_S:g} s (docs/authoring.md).",
        ),
    ] = False,
) -> None:
    """Grade every reference solution and wrong case in the sandbox."""
    catalogue = _load(content_dir)
    runner = _sandbox_runner()
    failures = 0
    for exercise_id in catalogue.graph.order:
        if only and not exercise_id.startswith(only):
            continue
        for result in check_exercise(catalogue.sources[exercise_id], runner):
            mark, colour = ("✓", "green") if result.ok else ("✗", "red")
            took = f" {result.seconds:.1f} s" if show_time else ""
            typer.secho(f"{mark} {result.exercise_id} [{result.case}]{took}", fg=colour)
            if show_time and result.case == "solution" and result.seconds > SOLUTION_BUDGET_S:
                typer.secho(
                    f"    ⚠ the solution took over the {SOLUTION_BUDGET_S:g} s budget to grade",
                    fg="yellow",
                )
            if not result.ok:
                failures += 1
                typer.echo(f"    {result.detail}")
    if failures:
        typer.secho(f"{failures} case(s) failed", fg="red", err=True)
        raise typer.Exit(1)


def _sandbox_runner() -> DockerSandboxRunner:
    return DockerSandboxRunner(
        DockerSandboxConfig(
            images={"python": get_settings().sandbox_image_python},
            oci_runtime=get_settings().sandbox_oci_runtime,
            max_memory_mb=get_settings().sandbox_max_memory_mb,
            timeout_factor=get_settings().sandbox_timeout_factor,
        )
    )


@content_app.command("new")
def new_exercise(
    branch: Annotated[str, typer.Argument(help="The branch to add the exercise to.")],
    slug: Annotated[str, typer.Argument(help="The exercise's directory name, in kebab-case.")],
    tier: Annotated[Tier, typer.Option(help="Difficulty tier.")] = Tier.BEGINNER,
    title: Annotated[str | None, typer.Option(help="Title (default: from the slug).")] = None,
    carry_from: Annotated[
        str | None,
        typer.Option(help="Project branches: the milestone whose solution this one starts from."),
    ] = None,
    content_dir: ContentDir = None,
) -> None:
    """Scaffold an exercise that validates now and grades once its solution is written."""
    root = content_dir or get_settings().content_dir
    catalogue = _load(root)
    try:
        made = scaffold_exercise(
            root, catalogue, branch, slug, tier=tier, title=title, carry_from=carry_from
        )
    except ScaffoldError as err:
        typer.secho(f"✗ {err}", fg="red", err=True)
        raise typer.Exit(1) from err
    typer.secho(f"✓ scaffolded {made.exercise_id} in {made.root}", fg="green")
    for path in made.files:
        typer.echo(f"    {path}")
    if made.linked_capstone:
        typer.echo(f"  added it to the prerequisites of capstone '{made.linked_capstone}'")
    for note in made.notes:
        typer.secho(f"⚠ {note}", fg="yellow")
    typer.echo(f"  next: uv run forgeway content test --only {made.exercise_id}")


def _source(catalogue: ContentCatalogue, exercise_id: str) -> None:
    if exercise_id not in catalogue.sources:
        typer.secho(f"✗ unknown exercise '{exercise_id}'", fg="red", err=True)
        raise typer.Exit(1)


@content_app.command()
def review(
    exercise_id: Annotated[
        str | None,
        typer.Argument(help="The exercise id, <branch>.<slug>; omit it to review every exercise."),
    ] = None,
    content_dir: ContentDir = None,
) -> None:
    """Print the cheat-review checklist for one exercise, with what cheap heuristics found.

    Without an id, review every exercise and print only the items to look at.

    Advisory: it exits 0 whatever it finds. A ✓ means a heuristic found nothing, not that
    nothing is there; see the limits in `lattice.application.content_review`.
    """
    catalogue = _load(content_dir)
    marks = {Status.OK: ("✓", "green"), Status.WARN: ("⚠", "yellow"), Status.MANUAL: ("·", None)}

    def show(item: ReviewItem) -> None:
        mark, colour = marks[item.status]
        typer.secho(f"{mark} {item.title}: {item.summary}", fg=colour)
        for finding in item.findings:
            typer.echo(f"    {finding.path}:{finding.line}  {finding.note}")
        for finding in item.accepted:
            typer.echo(f"    {finding.path}:{finding.line}  accepted (review-ok): {finding.note}")

    if exercise_id is None:
        flagged = 0
        for eid, source in sorted(catalogue.sources.items()):
            inputs = ReviewInput(source.exercise, source.tests(), source.wrong_cases())
            warned = [i for i in review_exercise(inputs) if i.status is Status.WARN]
            if warned:
                flagged += 1
                typer.echo(f"Cheat review: {eid} ({source.root})")
                for item in warned:
                    show(item)
        typer.echo(
            f"{len(catalogue.sources)} exercise(s) reviewed, {flagged} with item(s) to look at. "
            "Heuristics are advisory: ✓ means nothing was found, not that nothing is there."
        )
        return

    _source(catalogue, exercise_id)
    source = catalogue.sources[exercise_id]
    items = review_exercise(ReviewInput(source.exercise, source.tests(), source.wrong_cases()))
    typer.echo(f"Cheat review: {exercise_id} ({source.root})")
    for item in items:
        show(item)
    warnings = sum(1 for i in items if i.status is Status.WARN)
    typer.echo(
        f"{warnings} item(s) to look at; · items need reading by hand. "
        "Heuristics are advisory: ✓ means nothing was found, not that nothing is there."
    )


@content_app.command()
def probe(
    exercise_id: Annotated[str, typer.Argument(help="The exercise id, <branch>.<slug>.")],
    dirs: Annotated[
        list[Path], typer.Argument(help="Probe directories of learner files.", exists=True)
    ],
    base: Annotated[
        ProbeBase, typer.Option(help="What each probe's files are laid over.")
    ] = ProbeBase.STARTER,
    content_dir: ContentDir = None,
) -> None:
    """Grade probe directories in the sandbox and print every check's outcome and message.

    Exits 0 when every probe was graded, whatever the checks said; 1 if one was refused or
    could not be graded.
    """
    catalogue = _load(content_dir)
    _source(catalogue, exercise_id)
    probes = {
        str(path): {k: v for k, v in read_tree(path).items() if k != "expect.yaml"} for path in dirs
    }
    results = probe_exercise(catalogue.sources[exercise_id], probes, _sandbox_runner(), base=base)
    unrun = 0
    for result in results:
        report = result.report
        if report is None or report.status is GradeStatus.ERRORED:
            unrun += 1
            reason = result.refused if report is None else report.error
            typer.secho(f"✗ {result.name} (over the {base}): not graded: {reason}", fg="red")
            continue
        typer.secho(
            f"■ {result.name} (over the {base}): {report.status} in {report.duration_ms} ms",
            bold=True,
        )
        for check in report.checks:
            mark, colour = ("✓", "green") if check.passed else ("✗", "red")
            typer.secho(f"  {mark} {check.id}: {check.title}", fg=colour)
            for line in check.message.splitlines():
                typer.echo(f"      {line}")
    if unrun:
        typer.secho(f"{unrun} probe(s) not graded", fg="red", err=True)
        raise typer.Exit(1)
