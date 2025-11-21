**Contributing to CS7CS3-ASE-Group9**

Thank you for your interest in contributing to this project! By participating, you agree to abide by the guidelines below. This will help keep the project clean, understandable, and welcoming for everyone.

**1. Our workflow**

**These steps reflect the current workflow defined in the project’s README. **
GitHub

**Clone the repository to your local machine:**

git clone <repo-url>


**Checkout the main branch and pull latest changes:**

git checkout main  
git pull


**Create a working branch for your change. Name the branch after the ticket/issue it relates to. For example:**

git checkout -b KAN-13-featureName


_(Replace “KAN-13” with your ticket ID / issue number)_

**Make your changes locally. Stage and commit them with a meaningful commit message (starting with the ticket ID). Example:**

git add <files>  
git commit -m "KAN-13 Add sorting logic for city list"


**Push your branch to the remote repository (do not push to main):**

git push origin KAN-13-featureName


**On GitHub, open a Pull Request (PR) from your branch into main. Add a description of your change, how you tested it, and any dependencies or impacts.**

**2. Pull Request Guidelines**

At least one review is required before merging. 
GitHub

Use the “Squash and merge” strategy by default. 
GitHub

_**If your change might break existing functionality or is large in scope, clearly note that in the PR description and request more than one reviewer.**_

**In the description of your PR:**

Explain what you changed and why.

Describe how you tested your change (unit tests, manual testing, etc.).

If you added new dependencies/configuration, document them.

**Before merging:**

Resolve all comments from reviewers.

Ensure all CI/checks (if any) are green.

Ensure your branch is up to date with the latest main (rebase or merge as appropriate).

Once approved, squash your commits into a single meaningful commit (unless explicitly requested otherwise), then merge.

After merging, delete your feature branch to keep the repository tidy.

**3. Coding standards & best practices**

Follow the existing code style (indentation, naming conventions, file structure). Consistency makes the project easier to maintain.

Write clear, meaningful commit messages. Use the ticket/issue ID as a prefix (e.g., KAN-42 Fix memory leak in data loader).

Keep changes focused: one ticket/branch → one logical change. Avoid mixing unrelated changes in one PR.

Add or update tests for your changes when applicable. If you fix a bug, write a test that reproduces the bug then confirm your fix passes.

Document any new functionality or public API changes (add comments, update README or other docs as needed).

Ensure no sensitive information (passwords, API keys, credentials) is committed.

**4. Issue tracking**

If you find a bug or want to propose a new feature, open an Issue in GitHub.

In the issue: give a clear title, describe the problem or suggestion, include steps to reproduce (for bugs) and expected behaviour.

Assign the issue to yourself (or ask the project lead) and create a branch referencing that issue ID.

Link your pull request to the issue by including the issue number in the PR description (e.g., “Fixes #15”).

**5. Branching and releases**

The main branch (main) is always stable and should be ready to deploy / demo.

Feature branches should be named with the ticket/issue ID prefix (e.g., KAN-27-addLogin).

Once a feature PR is merged, the branch should be deleted.

For releases (if applicable): tag the commit, update versioning, and document in a CHANGELOG file.

**6. Code of Conduct**

We expect all contributors to behave professionally and respectfully. Be kind, helpful, and constructive in reviews and discussions. Disagreements happen—focus on the code, not the person.

**7. License and contributions**

By submitting a pull request, you agree that your contributions will be licensed under the same license as this project (as stated in the repository).
If you are not comfortable with that, please raise an issue before submitting your work.

**8. Thank you**

**Thank you for contributing! Your help improves the project and benefits everyone involved in the module.**
