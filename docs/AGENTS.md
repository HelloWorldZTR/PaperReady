## Documentations

In `docs/api.md`, document your newly created or modified api interfaces, brief their usage and interface.
In `docs/todo.md`, check off your newly made milestone. Once you made a major change, you need to submit a commit using git with proper commit message and document commit id in todolist. Also, you can refer to this document to pick up from the current implementation.
In `README.md`, document how this project can be run and built.
Also, use the todo.md as a scratch pad to save messages you think that is important for future implementations. I already included the original prompt of this project.
In `docs/PRD.md` is the requirement for this product, you should not modify it.

## Coding style

You need to write clear and tidy code, code length should be strictly restrcited to 500 lines, unless it is stylesheet or contains lengthy prompt. You cannot use less returns to shrink the line count.

Every primary function should contain a breif docstring describing its function and inputs/outputs. Also add inline comments when the logic gets complicated.

Prompts should be placed outside functions in a global variable fashion for easier modification.

## Building and testing

Write pytest scripts to create tests for important functionalities.
Use the conda environment generic for testing. You can install other packages inside, but remember to maintain the requirements.txt
Tauri is installed in paper-ready, with vue + js as the language preference and pnpm as the package manager. Feel free to install front-end plugins and custom components.