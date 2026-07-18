#!/usr/bin/env python3
import subprocess
import enum
import re
import os
import sys
from typing import Dict, List, Optional
def exitusage(code: int=1, usestdout: bool=False):
  out = (sys.stdout if usestdout else sys.stderr)
  out.write("  Usage:\n")
  out.write("  "+sys.argv[0]+" [OPT...] OLDPAT NEWREPL REPO...\n")
  out.write("  OLDPAT: Old URL pattern in Python regex format\n")
  out.write("  NEWREPL: New URL replacement in Python regex format\n")
  out.write("  REPO: Path to the repository, either the root of the repository or .git inside the repository. You can pass multiple repositories.\n")
  out.write("  Options:\n")
  out.write("  --write: Write changes to disk\n")
  out.write("  --search: Do a filesystem search on the provided directories to find all git repositories located there\n")
  out.write("  --printlvl dbg|verb|info|warn: Only print messages of this level and above (default: "+DEFAULTPRINTLVL.name.lower()+")\n")
  out.write("  --colourlvl info|warn|err|none: Highlight with red colour messages of this level and above (default: "+DEFAULTCOLOURLVL.name.lower()+")\n")
  out.write("  --git VAL: Change the git executable to use (default: git)\n")
  out.write("  --help: Show this help\n")
  out.write("  Examples\n")
  out.write("  Migrate a repository:\n")
  out.write("  "+sys.argv[0]+" 'olduser@oldhost\\.olddomain:olddir/' 'newuser@newhost.newdomain:newdir/' /path/to/repo\n")
  out.write("  Migrate multiple repositories:\n")
  out.write("  "+sys.argv[0]+" 'olduser@oldhost\\.olddomain:olddir/' 'newuser@newhost.newdomain:newdir/' ~/repo1 ~/repo2\n")
  out.write("  Search a directory for repositories and migrate them:\n")
  out.write("  "+sys.argv[0]+" --search 'olduser@oldhost\\.olddomain:olddir/' 'newuser@newhost.newdomain:newdir/' ~\n")
  out.write("  Search multiple directories for repositories and migrate them:\n")
  out.write("  "+sys.argv[0]+" --search 'olduser@oldhost\\.olddomain:olddir/' 'newuser@newhost.newdomain:newdir/' ~/dir1 ~/dir2\n")
  out.write("  If you need more control over filesystem search than --search provides, use \"find\" and \"xargs\":\n")
  out.write("  find ~/dir1 ~/dir2 -name .git -print0 | xargs -0 "+sys.argv[0]+" 'olduser@oldhost\\.olddomain:olddir/' 'newuser@newhost.newdomain:newdir/'\n")
  out.write("  By default migration is simulated, to actually write changes add --write:\n")
  out.write("  "+sys.argv[0]+" --write 'olduser@oldhost\\.olddomain:olddir/' 'newuser@newhost.newdomain:newdir/' /path/to/repo\n")
  exit(code)
def main() -> None:
  optwrite: Optional[bool] = None
  optsearch: Optional[bool] = None
  optprintlvl: Optional["Printlvl"] = None
  optcolourlvl: Optional["Printlvl"] = None
  optgit: Optional[str] = None
  args = sys.argv[1:]
  while len(args) >= 1 and args[0].startswith("-"):
    opt = args.pop(0)
    if opt == "--":
      break
    elif opt == "--write":
      optwrite = True
    elif opt == "--search":
      optsearch = True
    elif opt == "--printlvl":
      if len(args)<1:
        sys.stderr.write("Missing value of option "+opt+"\n")
        sys.stderr.write("\n")
        exitusage()
      val = args.pop(0).lower()
      try:
        optprintlvl = Printlvl[val.upper()]
      except KeyError:
        sys.stderr.write("Invalid value of option "+opt+": "+repr(val)+"\n")
        sys.stderr.write("\n")
        exitusage()
    elif opt == "--colourlvl":
      if len(args)<1:
        sys.stderr.write("Missing value of option "+opt+"\n")
        sys.stderr.write("\n")
        exitusage()
      val = args.pop(0).lower()
      try:
        optcolourlvl = Printlvl[val.upper()]
      except KeyError:
        sys.stderr.write("Invalid value of option "+opt+": "+repr(val)+"\n")
        sys.stderr.write("\n")
        exitusage()
    elif opt == "--git":
      if len(args)<1:
        sys.stderr.write("Missing value of option "+opt+"\n")
        sys.stderr.write("\n")
        exitusage()
      optgit = args.pop(0)
    elif opt == "--help":
      exitusage(code=0, usestdout=True)
    else:
      sys.stderr.write("Invalid option: "+opt+"\n")
      sys.stderr.write("\n")
      exitusage()
  if not (len(args)>=3): exitusage()
  oldpat = args[0]
  newrepl = args[1]
  repos = args[2:]
  Gitmigr(optprintlvl=optprintlvl, optcolourlvl=optcolourlvl, optgit=optgit).gitmigr(oldpat, newrepl, repos, optwrite=optwrite, optsearch=optsearch)
class Gitmigr:
  def __init__(self, optprintlvl: Optional["Printlvl"]=None, optcolourlvl: Optional["Printlvl"]=None, optgit: Optional[str]=None):
    self.optprintlvl: "Printlvl" = (DEFAULTPRINTLVL if optprintlvl is None else optprintlvl)
    self.optcolourlvl: "Printlvl" = (DEFAULTCOLOURLVL if optcolourlvl is None else optcolourlvl)
    self.optgit: str = (optgit if optgit else "git")
  def gitmigr(self, oldpat: str, newrepl: str, repos: List[str], optwrite: Optional[bool]=None, optsearch: Optional[bool]=None):
    if optwrite == None: optwrite = False
    if optsearch == None: optsearch = False
    if self.getgitmajorver() < 2: raise Exception("git 2 required")
    if optsearch:
      self.infoprint("* Started filesystem search...")
      repos2 = subprocess.run(["find"]+repos+["-name", ".git", "-print0"], check=True, stdout=subprocess.PIPE).stdout.decode().split("\x00")
      if repos2[-1] == "": repos2 = repos2[0:-1]
      self.infoprint("* Finished filesystem search")
    else:
      repos2 = repos
    self.dbgprint("* Started repo traversal...")
    repograph = self.searchrepos1(repos2)
    self.dbgprint("* Finished repo traversal")
    allconfigcount = 0
    migrconfigcount = 0
    migrconfigls: List[str] = []
    allgitmodulescount = 0
    migrgitmodulescount = 0
    migrgitmodulesls: List[str] = []
    repocounter = 0
    for repo in repograph:
      repocounter += 1
      self.verbprint("")
      self.verbprint("==== Processing repo "+str(repocounter)+" of "+str(len(repograph))+": "+repo)
      self.verbprint("")
      if (not os.path.isdir(os.path.join(repo, ".git"))) and repograph[repo].parent==None:
        self.warnprint("* Repo "+repo+" may be a submodule, but we're not processing its parent repo, so .gitmodules of the parent repo may be left non-migrated")
      if os.path.isdir(os.path.join(repo, ".git")) and repograph[repo].parent!=None:
        self.dbgprint("* Repo "+repo+" is a submodule with a regular .git directory (nothing wrong with that though)")
      configpath = os.path.join(self.getdotgitdir1(repo), "config")
      if not os.path.exists(configpath):
        raise Exception("Missing config file: "+configpath)
      gitmodulespath = os.path.join(repo, ".gitmodules")
      if len(repograph[repo].submods) > 0 and not os.path.exists(gitmodulespath):
        self.warnprint("* Repo "+repo+" has submodules but .gitmodules not found")
      if len(repograph[repo].submods) == 0 and os.path.exists(gitmodulespath):
        self.warnprint("* Repo "+repo+" has .gitmodules but no submodules have been found")
      allconfigcount += 1
      if self.procfil(oldpat, newrepl, configpath, optwrite=optwrite):
        migrconfigcount += 1
        migrconfigls.append(repo)
      if os.path.exists(gitmodulespath):
        allgitmodulescount += 1
        if self.procfil(oldpat, newrepl, gitmodulespath, optwrite=optwrite):
          migrgitmodulescount += 1
          migrgitmodulesls.append(repo)
    self.verbprint("")
    self.verbprint("==== Done")
    if migrconfigcount > 0:
      self.infoprint("")
      self.infoprint("* List of repositories where \"config\" files "+("have been" if optwrite else "would be")+" migrated:")
      for x in migrconfigls:
        self.infoprint("  * "+x)
    if migrgitmodulescount > 0:
      self.infoprint("")
      self.infoprint("* List of repositories where \".gitmodules\" files "+("have been" if optwrite else "would be")+" migrated:")
      for x in migrgitmodulesls:
        self.infoprint("  * "+x)
    self.infoprint("")
    self.infoprint("* Processed "+str(len(repograph))+" git repositories. "+("Migrated " if optwrite else "Would migrate ")+str(migrconfigcount)+" of "+str(allconfigcount)+" \"config\" files and "+str(migrgitmodulescount)+" of "+str(allgitmodulescount)+" \".gitmodules\" files.")
    if migrgitmodulescount > 0:
      self.warnprint("* Some .gitmodules files "+("have been" if optwrite else "would be")+" migrated, but you are responsible for commiting them.")
    if (not optwrite) and (migrconfigcount > 0 or migrgitmodulescount > 0):
      self.infoprint("* Repeat with --write option added before the arguments to actually write the changes.")
  def procfil(self, oldpat: str, newrepl: str, fil: str, optwrite: bool) -> bool:
    with open(fil, "r", encoding="UTF-8", newline="") as f:
      oldcont = f.read()
    newcont = re.sub(oldpat, newrepl, oldcont)
    if newcont != oldcont:
      self.backupfil(fil, optwrite=optwrite)
      self.infoprint("* "+("Rewriting: " if optwrite else "Would rewrite: ")+fil)
      if optwrite:
        with open(fil, "w", encoding="UTF-8", newline="") as f:
          f.write(newcont)
      return True
    else:
      self.dbgprint("* No need to rewrite: "+fil)
      return False
  def backupfil(self, fil: str, optwrite: bool) -> None:
    n = 1
    while True:
      bakfil = fil+".bak."+str(n)
      if not os.path.exists(bakfil):
        self.infoprint("* "+("Backing up " if optwrite else "Would back up ")+fil+" as "+bakfil)
        cmd = ["cp", "-a", fil, bakfil]
        self.dbgprint("* "+("Running: " if optwrite else "Would run: ")+repr(cmd))
        if optwrite:
          subprocess.run(cmd, check=True)
        return
      else:
        n += 1
        if n > 100:
          raise Exception("Can't back up file because too many versions already exist: "+fil)
  def searchrepos1(self, repos: List[str]) -> "RepoGraphType":
      # Takes a list of repo paths, normalizes them, searches them for submodules, deduplicates them, and orders them logically. Returns a graph. (It's implemented as a dict and a dict on Python 3.6+ preserves order like a list so there is no reason to return a list here.)
    repograph: "RepoGraphType" = {}
    def searchrepos1b(parent: Optional[str], repos: List[str]) -> None:
      for repo1 in repos:
        repo2 = os.path.normpath(repo1)
        if os.path.basename(repo2) == ".git":
          repo = os.path.normpath(os.path.dirname(repo2))
        else:
          repo = repo2
        if not os.path.exists(repo):
          raise Exception("repo does not exist: "+repo)
        if not os.path.exists(os.path.join(repo, ".git")):
          raise Exception("not a git repo: "+repo)
        if repo not in repograph:
          submods = self.getgitsubmods(repo, recursive=False)
          repograph[repo] = RepoGraphEnt(repo=repo, parent=parent, submods=submods)
          searchrepos1b(repo, submods)
        else:
            # Update the parent if needed. No need to search submodules again.
          if parent != None and parent != repograph[repo].parent:
            if repograph[repo].parent == None:
              repograph[repo].parent = parent
            else:
              raise Exception("disagreement on what the parent repo is")
    searchrepos1b(None, repos)
    repograph2 = self.ordrepos1(repograph)
    return repograph2
  def ordrepos1(self, repograph: "RepoGraphType") -> "RepoGraphType":
      # Order repos logically. A parent repo will always be placed before its submodules.
    toplvlrepos = [ repo for repo in repograph if repograph[repo].parent == None ]
    newrepograph: "RepoGraphType" = {}
    def ordrepos1b(parent: Optional[str], repos: List[str]) -> None:
      for repo in repos:
        if parent != repograph[repo].parent:
          raise Exception("parent mismatch")
        if repo in newrepograph:
          raise Exception("unexpected double traversal")
        newrepograph[repo] = repograph[repo]
        ordrepos1b(repo, repograph[repo].submods)
    self.dbgprint("* Traversing "+str(len(repograph))+" repos, starting from "+str(len(toplvlrepos))+" top-level repos")
    ordrepos1b(None, toplvlrepos)
    if newrepograph != repograph:
        # compares dict keys and values without comparing dict order
      raise Exception("the reordered graph doesn't have the same content as the original graph")
    return newrepograph
  def getgitmajorver(self) -> int:
    m = re.search(r"^git version (\d+)", subprocess.run([self.optgit, "--version"], check=True, stdout=subprocess.PIPE).stdout.decode())
    if m:
      return int(m.group(1))
    else:
      raise Exception("can't get git version")
  def getdotgitdir1(self, repo: str) -> str:
      # repo must be the root of the repository, not some other dir within it, for this function to return the correct result
    return os.path.join(repo, subprocess.run([self.optgit, "-C", repo, "rev-parse", "--git-dir"], check=True, stdout=subprocess.PIPE).stdout.decode().rstrip())
  def getgitsubmods(self, repo: str, recursive: bool=False) -> List[str]:
    a=re.split(r"\r\n|\r|\n", subprocess.run([self.optgit, "-C", repo, "submodule", "foreach", "--quiet"]+(["--recursive"] if recursive else [])+["pwd"], check=True, stdout=subprocess.PIPE).stdout.decode())
    if a[-1] == "": a = a[0:-1]
    return a
  def errprint(self, x: str):
    return self._print1(Printlvl.ERR,  "[ ERR] ", x)
  def warnprint(self, x: str):
    return self._print1(Printlvl.WARN, "[WARN] ", x)
  def infoprint(self, x: str):
    return self._print1(Printlvl.INFO, "[INFO] ", x)
  def verbprint(self, x: str):
    return self._print1(Printlvl.VERB, "[VERB] ", x)
  def dbgprint(self, x: str):
    return self._print1(Printlvl.DBG,  "[ DBG] ", x)
  def _print1(self, lvl: "Printlvl", pref: str, x: str):
    if lvl >= self.optprintlvl:
      if lvl >= self.optcolourlvl:
        col1="\x1b[01;31m"
        col2="\x1b[m"
      else:
        col1=""
        col2=""
      return print(col1+pref+x+col2, file=sys.stderr)
RepoGraphType = Dict[str,"RepoGraphEnt"]
class RepoGraphEnt:
  def __init__(self, repo: str, parent: Optional[str], submods: List[str]):
    self.repo = repo
    self.parent = parent
    self.submods = submods
class Printlvl(enum.IntEnum):
  DBG = 1
  VERB = 2
  INFO = 3
  WARN = 4
  ERR = 5
  NONE = 6
DEFAULTPRINTLVL = Printlvl.VERB
DEFAULTCOLOURLVL = Printlvl.WARN
if __name__=="__main__":
  main()
