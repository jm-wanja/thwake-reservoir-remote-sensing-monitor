#!/usr/bin/env bash
# PreToolUse hook (Bash): agents may only READ git/GitHub repositories.
# Any git or gh command not on the read-only allowlist is denied.
# Humans run commits/pushes themselves — see .ai/HUMAN-STEPS.md (H3).

cmd=$(jq -r '.tool_input.command // empty')
[ -z "$cmd" ] && exit 0

deny() {
  jq -n --arg r "$1" '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"deny",permissionDecisionReason:$r}}'
  exit 0
}

# Split compound commands on ; && || | and newlines, check each segment.
while IFS= read -r seg; do
  seg=$(printf '%s' "$seg" | sed -E 's/^[[:space:]]*(\(|\{)?[[:space:]]*//; s/^([A-Za-z_][A-Za-z0-9_]*=[^ ]* +)*//; s/^(sudo|command|env|exec|time|nohup) +//')
  set -- $seg
  tool=$(basename "${1:-}")

  if [ "$tool" = "git" ]; then
    shift
    # Skip global options (-C dir, -c k=v, --no-pager, etc.)
    while [ $# -gt 0 ]; do
      case "$1" in
        -C|-c|--git-dir|--work-tree|--namespace) shift 2 ;;
        --git-dir=*|--work-tree=*|--no-pager|--paginate|-P|--bare|--no-replace-objects) shift ;;
        *) break ;;
      esac
    done
    sub="${1:-}"; shift 2>/dev/null
    rest="$*"
    case "$sub" in
      ""|status|diff|log|show|blame|ls-files|ls-tree|rev-parse|rev-list|describe|shortlog|grep|cat-file|reflog|whatchanged|check-ignore|version|help|--version|--help) ;;
      branch)
        printf '%s' "$rest" | grep -Eq '(^| )(-d|-D|-m|-M|-c|-C|--delete|--move|--copy|--set-upstream-to|-u|--unset-upstream|--edit-description|-f|--force)( |$)' \
          && deny "Agents may only read repos: 'git branch' with a modifying flag is blocked. Ask the human (HUMAN-STEPS.md H3)." ;;
      remote)
        case "${rest%% *}" in ""|-v|--verbose|show|get-url) ;; *) deny "Agents may only read repos: 'git remote $rest' is blocked." ;; esac ;;
      config)
        printf '%s' "$rest" | grep -Eq '(^| )(--get|--get-all|--get-regexp|--list|-l)( |$)' \
          || deny "Agents may only read repos: 'git config' writes are blocked (use --get/--list)." ;;
      stash)
        case "${rest%% *}" in list|show) ;; *) deny "Agents may only read repos: 'git stash' changes are blocked." ;; esac ;;
      *)
        deny "Agents may only read repos: 'git $sub' is blocked. The human commits/pushes/tags (see .ai/HUMAN-STEPS.md H3). Suggest the command instead." ;;
    esac
  fi

  if [ "$tool" = "gh" ]; then
    a="${2:-}"; b="${3:-}"
    case "$a $b" in
      "auth status"|"repo view"|"repo list"|"issue list"|"issue view"|"pr list"|"pr view"|"pr diff"|"pr checks"|"pr status"|"run list"|"run view"|"workflow list"|"workflow view"|"release list"|"release view"|"browse "*|"search "*|"--version "|"help "*) ;;
      *) deny "Agents may only read repos: 'gh $a $b' is blocked (incl. gh api). The human does GitHub changes (HUMAN-STEPS.md H3/H4)." ;;
    esac
  fi

  # Direct tampering with the .git directory
  if printf '%s' "$seg" | grep -Eq '(^|[[:space:]])(rm|mv|cp|rsync|truncate|chmod|chown|ln|tee|dd|shred|find)[[:space:]].*\.git(/|[[:space:]]|$)'; then
    deny "Agents may not modify the .git directory."
  fi
  if printf '%s' "$seg" | grep -Eq '>{1,2}[[:space:]]*[^[:space:]]*\.git/'; then
    deny "Agents may not write into the .git directory."
  fi
done < <(printf '%s\n' "$cmd" | sed -E 's/(\&\&|\|\||;|\|)/\n/g')

exit 0
