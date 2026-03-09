ENV_NAME = shiki_env

.PHONY: create-env init-poetry setup-poetry register-env setup-deps remove-env-with-kernel remove-poetry-files

create-env:
	conda create -y -n $(ENV_NAME) python==3.12.*

init-poetry:
	pip install poetry
	poetry init --no-interaction --python ">=3.12,<3.15"
	poetry add --group dev ipywidgets black isort ipykernel tqdm trackio

setup-poetry:
	pip install poetry
	poetry update --lock
	poetry install --no-root

register-env:
	python -m ipykernel install --user --name=$(ENV_NAME)

setup-deps: setup-poetry register-env

remove-env-with-kernel:
	jupyter kernelspec remove -f $(ENV_NAME) || true
	conda env remove -y -n $(ENV_NAME)

remove-poetry-files:
	rm pyproject.toml poetry.lock
