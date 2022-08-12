Thanks for your interest in contributing to condax!

## Development environment
To set up a development environment and then activate it, you can use [poetry](https://python-poetry.org/).

```bash
poetry install
poetry shell
```

From now on it is assumed you are in the development environment.

## Testing condax locally
In your environmnent run the tests as follows

```bash
pytest tests
```

## Testing condax on Github Actions
When you make a pull request, tests will automatically be run against your code as defined in `.github/workflows/pythonpackage.yml`.  These tests are run using github actions

## Creating a pull request
When making a new pull request please create a news file in the `./news` directory. You can make a copy of the provided template. This will automatically be merged into the documentation when new releases are made.

## Documentation
`condax` autogenerates API documentation, published on github pages.

## Release New `condax` Version
To create a new release condax uses [rever](https://regro.github.io/rever-docs)

```
conda install rever
rever {new_version_number}
```
