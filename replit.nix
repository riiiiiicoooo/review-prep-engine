{ pkgs }:
with pkgs;
let
  pythonPackages = python311.withPackages (p: with p; [
    flask
    flask-cors
    psycopg2
    requests
    python-dotenv
    pydantic
    numpy
    pandas
    pytest
  ]);
in
mkShell {
  buildInputs = [
    pythonPackages
    nodejs_20
    postgresql_15
    git
    curl
    jq
  ];

  shellHook = ''
    export PYTHONPATH=$PYTHONPATH:$(pwd)
    export PATH=$PATH:$(npm bin)

    # Initialize PostgreSQL if needed
    if [ ! -d "$PGDATA" ]; then
      export PGDATA=$(pwd)/.postgres
      initdb $PGDATA
    fi

    echo "Review Prep Engine development environment loaded"
    echo "Available commands:"
    echo "  npm install       - Install Node dependencies"
    echo "  pip install -r requirements.txt  - Install Python dependencies"
    echo "  supabase start    - Start local Supabase instance"
    echo "  python api/app.py - Start Flask API"
    echo "  npm run n8n      - Start n8n (requires additional setup)"
  '';
}
