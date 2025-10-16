#!/usr/bin/env bash
# This script crawls all repositories and performs general checks
# such as repository formatting and searching for new versions.
#
# This is done centrally, rather than separately in each repository,
# to reduce the amount of bolt-on code. GH doesn't support centralized rules,
# so you'll need to copy the rules to each repository.
#
# Actual checks:
# - repository settings
# - new version from upstream

set -euo pipefail

function fatal() {
  local message=$1
  >&2 echo "ERROR: $message"
  exit 1
}

function log() {
  local message=$1
  >&2 echo "LOG: $message"
}

GITHUB_ORG="zig-devel"
GITHUB_TOKEN=""

INVALIDATE_CACHE=false

CHECK_UPDATES=true
CHECK_REPOSITORY_SETTINGS=true

REPOS_DIR=".overseer_cache"
REPOS_CACHE="$REPOS_DIR/repos.jsonl"

while [[ $# -gt 0 ]]; do
  case $1 in
    --github-org)
      GITHUB_ORG="$2"
      shift # past argument
      shift # past value
      ;;
    --github-token)
      GITHUB_TOKEN="$2"
      shift # past argument
      shift # past value
      ;;
    --invalidate-cache)
      INVALIDATE_CACHE=true
      shift # past argument
      ;;
    --no-check-updates)
      CHECK_UPDATES=false
      shift # past argument
      ;;
    --no-check-repository-settings)
      CHECK_REPOSITORY_SETTINGS=false
      shift # past argument
      ;;
    --repos-dir)
      REPOS_DIR="$2"
      shift # past argument
      shift # past value
      ;;
    --repos-cache)
      REPOS_CACHE="$2"
      shift # past argument
      shift # past value
      ;;
    *)
      fatal "Unknown option $1"
      ;;
  esac
done

if [ $INVALIDATE_CACHE = true ]; then
  rm -rf "$REPOS_DIR" "$REPOS_CACHE"
fi

mkdir -p "$REPOS_DIR"

if [[ -f "$REPOS_CACHE" ]]; then
  log "Use cached repos list from $REPOS_CACHE"
else
  log "Download repositories from API"

  page=1
  while true; do
    api_url="https://api.github.com/orgs/$GITHUB_ORG/repos?per_page=100&page=$page"
    api_bearer=""

    if [ -n "$GITHUB_TOKEN" ]; then
      api_bearer="Authorization: Bearer $GITHUB_TOKEN"
    fi

    response=$(curl -s --fail-with-body -H "$api_bearer" "$api_url" | jq -r -c '.[]')
    if [ -z "$response" ]; then
      break
    fi

    echo "$response" >> "$REPOS_CACHE"

    ((page++))
  done
fi

function at() {
  local json=$1
  local key=$2

  echo "$json" | jq -r ".${key}"
}

while read -r repository; do
  # extract info about repositories
  name=$(at "$repository" 'name')
  clone_url=$(at "$repository" 'clone_url')
  default_branch=$(at "$repository" 'default_branch')

  private=$(at "$repository" 'private')
  archived=$(at "$repository" 'archived')
  is_template=$(at "$repository" 'is_template')

  has_issues=$(at "$repository" 'has_issues')
  has_wiki=$(at "$repository" 'has_wiki')
  has_pages=$(at "$repository" 'has_pages')
  has_projects=$(at "$repository" 'has_projects')
  has_discussions=$(at "$repository" 'has_discussions')

  # validate repository structure
  if [[ "$name" =~ ^\. || $private == "true" || $archived == "true" ]]; then
    continue
  fi

  log "Check $name repository config..."

  if [[ $CHECK_REPOSITORY_SETTINGS = true ]]; then
    [ "$default_branch" = "main" ] || fatal "Default branch must me 'main' not $default_branch"
    [ "$is_template" = "false" ] || fatal "Repository should not be a template"

    [ "$has_issues" = "true" ] || fatal "Issues must be enabled"
    [ "$has_wiki" = "false" ] || fatal "Wiki must be disabled"
    [ "$has_pages" = "false" ] || fatal "Pages must be disabled"
    [ "$has_projects" = "false" ] || fatal "Projects must be disabled"
    [ "$has_discussions" = "false" ] || fatal "Discussions must be disabled"
  fi

  # clone repo to intermediate directory
  git_dir="$REPOS_DIR/$name"
  if [[ -d $git_dir ]]; then
    cd "$git_dir"

    git fetch -q origin
    git reset -q --hard "origin/$default_branch"
    git clean -q -xd --force
  else
    git clone --depth 1 --branch "$default_branch" "$clone_url" "$git_dir"
    cd "$git_dir"
  fi

  if [[ $CHECK_UPDATES = true ]]; then
    nvchecker -c .nvchecker.toml
    update=$(nvcmp -c .nvchecker.toml)

    if [[ -n $update ]]; then
      fatal "$name has new version!"
    fi
  fi

  cd - >> /dev/null
done < "$REPOS_CACHE"
