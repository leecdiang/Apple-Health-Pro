"""Console executable entry point; intentionally independent of PyQt and psutil."""
from healthpro.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
