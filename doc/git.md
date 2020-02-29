


    - [commit](#commit)
    - [amend](#amend)
    - [cherry-pick](#cherry)
    - [revert](#revert)


<a id=push></a>
#### push
use the -u flag (upstream) when you make your first push

how to push newly created branch to upstream

```bash
-u, --set-upstream
git push -u origin BRANCH
```

or directly `push`

```bash
git push origin BRANCH
```

- switch to another branch

```bash
git checkout <New-Branch>
```

or with force

```
-f, --force
    When switching branches, proceed even if the index or the working tree differs from HEAD. This is used to throw away local changes.
    When checking out paths from the index, do not fail upon unmerged entries; instead, unmerged entries are ignored.
```

- create new branch from history commit and switch to it meanwhile
```


- rename branch

```bash
-m, --move
    Move/rename a branch and the corresponding reflog.

# rename current branch to <NEW-BRANCH-NAME>
git branch -m <NEW-BRANCH-NAME>

# Alternative
git branch --move <OLD-BRANCH-NAME> <NEW-BRANCH-NAME>
```



<a id=commit></a>

#### commit

```bash
git status
git diff
git add .
git commit -m 'This is my first commit'
git show 82fb783

commit 82fb78377e99c98a902bc174e67d3913ed419ce7
Author: Peng Xiang <hi.pxiang@gmail.com>
Date:   Fri Dec 13 11:13:23 2019 +0800

    add rime pro package

diff --git a/template/rime_pro.zip b/template/rime_pro.zip
new file mode 100644
index 0000000..4a32888
Binary files /dev/null and b/template/rime_pro.zip differ
```

<a id=amend></a>

#### amend

if you need to correct the commit message

```bash
git commit --amend

# then use --force
# push to GitHub
git push origin master --force
```

if you need to modify some info of the submitter, such as `username` and `email` after pushing code to GitHub

```bash
git commit --amend --author='Peng Xiang <hi.pxiang@gmail.com>'
```

**Notice** `<>` was the essential sign for email address

```bash
# then use --force
git push origin master --force
```



- directly update our local repo with any changes made in the central repo

  set **upstream** branch

  ```bash
  git remote add upstream <url-to-central-repo>
  git pull upstream
  ```

- change your remote's URL

  ```bash
  # check
  git remote -v
  origin  https://github.com/iqiyi/dpvs (fetch)
  origin  https://github.com/iqiyi/dpvs (push)
  
  git remote set-url origin https://github.com/xiangp126/dpvs
  
  # check
  git remote -v
  origin  https://github.com/xiangp126/dpvs (fetch)
  origin  https://github.com/xiangp126/dpvs (push)
  ```

<a id=cherry></a>

#### cherry-pick
Apply the changes introduced by some existing commits

- cherry-pick specific commit from different branch
git checkout <branch-to-cherry-pick>
git cherry-pick <commit-id-to-cherry-pick-from>..<last_commit>
```
- cherry-pick specific commit from a different repository

  You'll need to add the other repository as a remote, then  fetch its changes. From there you see the commit and you can cherry-pick it.

```bash
# Here's an example of the remote-fetch-merge.
cd /home/you/projectA
git remote add projectB /home/you/projectB
git fetch projectB

# Then you can:
git cherry-pick <first_commit>..<last_commit>
```

- how to record the commit

```bash
-x
    When recording the commit, append a line that says "(cherry picked from commit ...)" to the original commit message in order to indicate which commit this change was cherry-picked from.
    This is done only for cherry picks without conflicts.
    Do not use this option if you are cherry-picking from your private branch because the information is useless to the recipient. 
    If on the other hand you are cherry-picking between two publicly visible branches
    (e.g. backporting a fix to a maintenance branch for an older release from a development branch), adding this information can be useful.
```

- cherry-pick specific merge from different branch

```bash
-m parent-number 

--mainline parent-number 

Usually you cannot cherry-pick a merge because you do not know which side of the merge should be considered the mainline.  This option specifies the parent number (starting from 1) of the mainline and allows cherry-pick to replay the change relative to the specified parent.
```

and you can try

```bash
git cherry-pick -m 1 <merge-hashid>
```

**how to explain**

```bash

For example, if your commit tree is like below:

- A - D - E - F -   master
   \     /
    B - C           branch one

then git cherry-pick E will produce the issue you faced.

git cherry-pick E -m 1 means using D-E, while git cherry-pick E -m 2 means using B-C-E.
```

<a id=revert></a>

#### revert

[Git Revert Tutorials](https://www.atlassian.com/git/tutorials/undoing-changes/git-revert)

```
NAME
       git-revert - Revert some existing commits

SYNOPSIS
       git revert [--[no-]edit] [-n] [-m parent-number] [-s] [-S[<keyid>]] <commit>...
       git revert --continue
       git revert --quit
       git revert --abort