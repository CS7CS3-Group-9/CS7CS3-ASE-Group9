# Sustainable City Management

This is the README for group 9's project on sustainable city management :)

### Git steps for making a contribution
1. Clone the repo to your local machine with `git clone` using either HTTPS or SSH
2. If you already have the repo cloned checkout the main branch with `git checkout main`
3. Make sure you have all the latest commits with `git pull`
4. Create a branch for you feature or bug fix with named after the JIRA ticket e.g. KAN-13: `git checkout -b KAN-13`
5. Make your changes then stage them: `git add <files to be staged>` or `git add .` for all changes files
6. Commit your changes and add a **meaningful** commit message starting with the ticket ID e.g `git commit -m "KAN-13 This is a meaningful commit message`
7. Push your branch to the remote repo **NOT** to the main branch: `git push origin KAN-13`
8. On github, raise the pull request, add a description and wait for a review before merging.


### Pull request guidelines
- Currently 1 review is required to merge.
- The default strategy for merging a PR should be "Squash and Merge"
- When making a PR that changes or could potentially break existing code please note that in the description box
- If the PR is large and the description doesnt fit in the title box, write a more detailed description in the description box
- Describe how you tested your changes, if testing was required in the description box
- Resolve any comments before merging the PR
- If it is a large potentially breaking change, request more than 1 reviewer
- TODO: Create a PR template