# Install from PyPI
pip install pulp-cli[pygments]  # colorized output
pip install pulp-cli  # no color output

# Install from source
git clone https://github.com/pulp/pulp-cli.git # or your fork url
cd pulp-cli
pip install -e .
cd ..

# Set up CLI config file
mkdir ~/.config/pulp
cat > ~/.config/pulp/settings.toml << EOF
[cli]
base_url = "http://pulp:80" # common to be localhost
verify_ssl = false
format = "json"
EOF
