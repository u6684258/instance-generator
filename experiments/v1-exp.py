#! /usr/bin/env python

"""
First test experiment for instance generator
"""

import glob
import os
import platform
import sys

from downward.reports.absolute import AbsoluteReport
from lab.environments import BaselSlurmEnvironment, LocalEnvironment
from lab.experiment import Experiment
from lab.parser import Parser
from lab.reports import Attribute


# Create custom report class with suitable info and error attributes.
class BaseReport(AbsoluteReport):
    INFO_ATTRIBUTES = ["time_limit", "memory_limit"]#, "seed"]
    ERROR_ATTRIBUTES = [
        "domain",
        "problem",
        "algorithm",
        "unexplained_errors",
        "error",
        "node",
    ]


NODE = platform.node()
REMOTE = NODE.endswith(".scicore.unibas.ch") or NODE.endswith(".cluster.bc2.ch")
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BENCHMARKS_DIR = os.path.join(SCRIPT_DIR, "formally-represented-domains")
DOMAINS = sorted(glob.glob(os.path.join(BENCHMARKS_DIR, "*", "domain.pddl")))
NUM_OBJECTS = [5,8,10]
#ALGORITHMS = ["2approx", "greedy"]
#SEED = 2018
TIME_LIMIT = 1800
MEMORY_LIMIT = 2048

if REMOTE:
    ENV = BaselSlurmEnvironment(email="claudia.grundke@unibas.ch", partition="infai_2")
    SUITE = DOMAINS
else:
    ENV = LocalEnvironment(processes=2)
    # Use smaller suite for local tests.
    SUITE = DOMAINS[:1]
ATTRIBUTES = [
#    "error",
#    "solve_time",
    "num_instances",
    "representativeness",
    "generator_exit_code"
#    Attribute("solved", absolute=True),
]

"""
Create parser for the following example solver output:

Finished generating 35 representative instances.
The representativeness score of the set of generated instances is 0.45227817470289766.
"""


def make_parser():
    def solved(content, props):
        props["solved"] = int("cover" in props)

    def error(content, props):
        if props["solved"]:
            props["error"] = "cover-found"
        else:
            props["error"] = "unsolved"

    parser = Parser()
    parser.add_pattern(
        "node", r"node: (.+)\n", type=str, file="driver.log", required=True
    )
    parser.add_pattern(
        "generator_exit_code", r"solve exit code: (.+)\n", type=int, file="driver.log"
    )
#    parser.add_pattern("cover", r"Cover: (\{.*\})", type=str)
    parser.add_pattern("num_instances", r"Finished generating (\d+) representative instances.\n", type=int)
    parser.add_pattern("representativeness", r"The representativeness score of the set of generated instances is (.+).\n", type=float)
#    parser.add_function(solved)
#    parser.add_function(error)
    return parser


# Create a new experiment.
exp = Experiment(environment=ENV)
# Add solver to experiment and make it available to all runs.
#exp.add_resource("generator", os.path.join(SCRIPT_DIR, "instance-generator", "src", "instance_generation.py"))
# Add custom parser.
exp.add_parser(make_parser())

for num_objects in NUM_OBJECTS:
    for domain in SUITE:
        run = exp.add_run()
        # Create a symbolic link and an alias. This is optional. We
        # could also use absolute paths in add_command().
        run.add_resource("domain", domain, symlink=True)
        run.add_command(
            "generate",
            [sys.executable, "-m", "instance_generator", "{domain}", "0", "-n", num_objects, "--representative"],
            time_limit=TIME_LIMIT,
            memory_limit=MEMORY_LIMIT,
        )
        # AbsoluteReport needs the following attributes:
        # 'domain', 'problem' and 'algorithm'.
        domain_name = os.path.basename(os.path.dirname(domain))
#        task_name = os.path.basename(task)
        run.set_property("domain", domain_name)
        run.set_property("problem", f"{num_objects}-objects")
        run.set_property("algorithm", "beautiful_algo")
        # BaseReport needs the following properties:
        # 'time_limit', 'memory_limit', 'seed'.
        run.set_property("time_limit", TIME_LIMIT)
        run.set_property("memory_limit", MEMORY_LIMIT)
#        run.set_property("seed", SEED)
        # Every run has to have a unique id in the form of a list.
        run.set_property("id", [domain_name, str(num_objects)])

# Add step that writes experiment files to disk.
exp.add_step("build", exp.build)

# Add step that executes all runs.
exp.add_step("start", exp.start_runs)

# Add step that parses the logs.
exp.add_step("parse", exp.parse)

# Add step that collects properties from run directories and
# writes them to *-eval/properties.
exp.add_fetcher(name="fetch")

# Make a report.
exp.add_report(BaseReport(attributes=ATTRIBUTES), outfile="report.html")

# Parse the commandline and run the given steps.
exp.run_steps()

