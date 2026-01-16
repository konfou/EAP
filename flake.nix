{
  description = "EAP Nix dev environ";
  inputs = {
    nixpkgs.url = "nixpkgs";
  };
  outputs =
    { self, nixpkgs }:
    let
      system = "x86_64-linux";
      pkgs = nixpkgs.legacyPackages.${system};
    in
    {
      devShells.${system}.default =
        with pkgs;
        mkShell {
          packages = with pkgs; [
            (python314.withPackages (
              ps: with ps; [
                apscheduler
                dash
                fastapi
                httpx
                ipython
                numpy
                pip-tools
                prometheus-client
                psycopg
                pydantic
                pydantic-settings
                pytest
                pytest-asyncio
                pytest-cov
                python-dateutil
                ruff # native
                sqlalchemy
                structlog
                uvicorn
              ]
            ))
            # in:pyproject but not-exposed-when-in:nixPythonPackages
            pre-commit
            taplo
            ty
            # rest
            postgresql_16
            curl
          ];

          shellHook = ''
            export DATABASE_URL=''${DATABASE_URL:-"postgresql+psycopg://app:app@localhost:5432/risk"}
            echo "EAP dev shell ready (Nix Python w/ deps). DATABASE_URL=$DATABASE_URL"
          '';
        };
    };
}
