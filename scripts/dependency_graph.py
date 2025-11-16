#!/usr/bin/env python3
import json
import pathlib
from typing import TypedDict
from yaml import load, dump
import os
try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper

class DependencyFile(TypedDict):
    dependencies: set[str]
    file: pathlib.Path

class InvalidApplicationSetDependencies(ValueError):
    def __init__(self, errors: list[tuple[str, str]]):
        self.errors =errors
    def __repr__(self):
        msg = [str(self.__class__)]
        for app_name, dep_name in self.errors:
            msg.append(f"Dependency({dep_name}) in App({app_name}) is invalid")
        return os.linesep.join(msg)

def load_dependencies() -> dict[str, DependencyFile]:
    """Load the JSON file containing application dependencies."""
    results = {}
    for dirpath, dirnames, filenames in pathlib.Path("kubernetes/main/apps").resolve().walk():
        for filename in filenames:
            if filename in ("config.json", "config.json.disabled"):
                with (dirpath / filename).open("r") as file:
                    raw = file.read()
                    data = json.loads(raw)
                    results[data["appName"]] = {
                        "dependencies": set(data.get("dependencies", [])),
                        "file": (dirpath / filename)
                    }
    return results

def make_groups(dependencies: dict[str, DependencyFile], group_count: int = 1, matched_deps: set[str] = set(), results: dict[int, set[str]] | None = None):
    if not results:
        results = {}
    results[group_count] = set()
    new_matched_deps: set[str] = set()
    for dependency in list(dependencies.keys()):
        child_deps = dependencies[dependency]['dependencies']
        if matched_deps >= child_deps:
            results[group_count].add(dependency)
            new_matched_deps.add(dependency)
            del dependencies[dependency]
    matched_deps = matched_deps | new_matched_deps
    if dependencies:
        return make_groups(dependencies, group_count + 1, matched_deps, results)
    return results


def update_appset(groups: dict[int, set[str]], appset_path: pathlib.Path):
    with appset_path.open('r') as fh:
        appset = load(fh, Loader=Loader)
    appset['spec']['strategy']['rollingSync']['steps'] = [
            {"matchExpressions": [{"key": "appName", "operator": "In", "values": sorted(list(app_names))}]} for app_names in groups.values()
    ]
    with appset_path.open('w') as fh:
        fh.write(dump(appset, Dumper=Dumper))

def update_app_config(groups: dict[int, set[str]], dependencies: dict[str, DependencyFile]) -> None:
    for group in groups:
        for app in groups[group]:
            with dependencies[app]['file'].open('r') as fr:
                raw = fr.read()
                app_config = json.loads(raw)
            if group != app_config.get("wave"):
                app_config["wave"] = group
                with dependencies[app]["file"].open("w") as fw:
                    json.dump(app_config, fw)


def check_appset_sync_strategy(max_wave: int, appset_file_path: pathlib.Path):
    with appset_file_path.open('r') as fh:
        app_set = load(fh, Loader=Loader)
    if int(app_set['spec']['strategy']['rollingSync']['steps'][-1]['matchExpressions'][-1]['values'][-1]) < max_wave:
        raise ValueError(f"max wave {max_wave} is missing from the rollingSync strategy matches")


def validate_dependencies(dependencies: dict[str, DependencyFile]):
    errors = []
    for app_name in dependencies:
        for dep_name in dependencies[app_name]['dependencies']:
            if dep_name not in dependencies:
                errors.append((app_name, dep_name))
    if errors:
        raise InvalidApplicationSetDependencies(errors)

def main():
    dependencies = load_dependencies()
    validate_dependencies(dependencies)
    results = make_groups(dependencies)
    dependencies = load_dependencies()
    # for group, app_names in results.items():
    #     print(f"{group}:")
    #     for app_name in sorted(list(app_names)):
    #         print(f"    {app_name}")
    # update_appset(results, pathlib.Path("kubernetes/main/bootstrap/appset.yaml"))
    update_app_config(results, dependencies)
    check_appset_sync_strategy(list(results.keys())[-1], pathlib.Path("kubernetes/main/bootstrap/appset.yaml"))


if __name__ == "__main__":
    main()
