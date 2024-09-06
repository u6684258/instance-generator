#! /usr/bin/env python3

import sys

import pddl
import pddl_parser

def main():
    if len(sys.argv) != 2:
        print("Usage: instance_genartion.py <domain-file>")
        sys.exit(1)

    domain_file = sys.argv[1]
    domain = pddl_parser.open(domain_file)
    domain.dump()


if __name__ == "__main__":
    main()
