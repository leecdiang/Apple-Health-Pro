"""Desktop launcher with lazy CLI routing: export never imports Qt."""
import sys


def main():
    if len(sys.argv) > 1 and sys.argv[1] in {"export", "sources"}:
        from healthpro.cli import main as cli_main
        return cli_main()
    from healthpro.gui import main as gui_main
    return gui_main()

if __name__ == '__main__':
    raise SystemExit(main())
