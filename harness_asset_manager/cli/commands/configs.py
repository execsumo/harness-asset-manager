import argparse


def list_configs(container, args):
    print("Configs list:")
    print(container.configs_queries.list_configs())
    return 0

def capture_configs(container, args):
    container.configs_mutations.capture(explicit=args.explicit)
    return 0

def restore_config(container, args):
    container.configs_mutations.restore(args.harness)
    return 0

def diff_config(container, args):
    print(container.configs_queries.get_diff(args.harness))
    return 0

def register(subparsers, common: argparse.ArgumentParser) -> None:
    parser = subparsers.add_parser("configs", parents=[common], help="Manage configuration preferences.")
    subs = parser.add_subparsers(dest="action", required=True)
    
    list_p = subs.add_parser("list", help="List configs in manifest.")
    list_p.set_defaults(handler=list_configs)
    
    capture_p = subs.add_parser("capture", help="Capture local configs.")
    capture_p.add_argument("--explicit", action="store_true")
    capture_p.set_defaults(handler=capture_configs)
    
    restore_p = subs.add_parser("restore", help="Restore config from manifest.")
    restore_p.add_argument("harness")
    restore_p.set_defaults(handler=restore_config)
    
    diff_p = subs.add_parser("diff", help="Show diff for a harness.")
    diff_p.add_argument("harness")
    diff_p.set_defaults(handler=diff_config)
