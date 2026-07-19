  Usage:
  ./gitmigr.py [OPT...] OLDPAT NEWREPL REPO...
  OLDPAT: Old URL pattern in Python regex format
  NEWREPL: New URL replacement in Python regex format
  REPO: Path to the repository, either the root of the repository or .git inside the repository. You can pass multiple repositories.
  Options:
  --write: Write changes to disk
  --search: Do a filesystem search on the provided directories to find all git repositories located there
  --printlvl dbg|verb|info|warn: Only print messages of this level and above (default: verb)
  --colourlvl info|warn|err|none: Highlight with red colour messages of this level and above (default: warn)
  --git VAL: Change the git executable to use (default: git)
  --help: Show this help

  Examples
  Migrate a repository:
  ./gitmigr.py 'olduser@oldhost\.olddomain:olddir/' 'newuser@newhost.newdomain:newdir/' /path/to/repo
  Migrate multiple repositories:
  ./gitmigr.py 'olduser@oldhost\.olddomain:olddir/' 'newuser@newhost.newdomain:newdir/' ~/repo1 ~/repo2
  Search a directory for repositories and migrate them:
  ./gitmigr.py --search 'olduser@oldhost\.olddomain:olddir/' 'newuser@newhost.newdomain:newdir/' ~
  Search multiple directories for repositories and migrate them:
  ./gitmigr.py --search 'olduser@oldhost\.olddomain:olddir/' 'newuser@newhost.newdomain:newdir/' ~/dir1 ~/dir2
  If you need more control over filesystem search than --search provides, use "find" and "xargs":
  find ~/dir1 ~/dir2 -name .git -print0 | xargs -0 ./gitmigr.py 'olduser@oldhost\.olddomain:olddir/' 'newuser@newhost.newdomain:newdir/'
  By default migration is simulated, to actually write changes add --write:
  ./gitmigr.py --write 'olduser@oldhost\.olddomain:olddir/' 'newuser@newhost.newdomain:newdir/' /path/to/repo
