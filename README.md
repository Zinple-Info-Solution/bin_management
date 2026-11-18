### Bin Management

Bin locations on top of the ERPNext warehouse tree

Bins are ordinary leaf warehouses, so stock balances, transfers and Putaway Rules keep working.

- **Bin Layout Generator**: builds an Aisle > Rack > Shelf > Bin warehouse tree (codes such as `A-03-2-1`) under a group warehouse in one step. Running it again with wider ranges adds only the missing nodes. Open it from a group Warehouse with **Generate Bin Layout**.
- **Location fields on Warehouse**: Location Type, Location Code, Bin Barcode (must be unique), capacity and dimensions, in a "Bin Location" section.
- **Stock by Bin report**: item quantities per bin, filterable by warehouse, aisle, rack, item and item group, with an option to list empty bins.

### Installation

You can install this app using the [bench](https://github.com/frappe/bench) CLI:

```bash
cd $PATH_TO_YOUR_BENCH
bench get-app $URL_OF_THIS_REPO --branch version-16
bench install-app bin_management
```

### Contributing

This app uses `pre-commit` for code formatting and linting. Please [install pre-commit](https://pre-commit.com/#installation) and enable it for this repository:

```bash
cd apps/bin_management
pre-commit install
```

Pre-commit is configured to use the following tools for checking and formatting your code:

- ruff
- eslint
- prettier
- pyupgrade
### CI

This app can use GitHub Actions for CI. The following workflows are configured:

- CI: Installs this app and runs unit tests on every push to `develop` branch.
- Linters: Runs [Frappe Semgrep Rules](https://github.com/frappe/semgrep-rules) and [pip-audit](https://pypi.org/project/pip-audit/) on every pull request.


### License

mit
