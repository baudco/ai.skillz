let SessionLoad = 1
let s:so_save = &g:so | let s:siso_save = &g:siso | setg so=0 siso=0 | setl so=-1 siso=-1
let v:this_session=expand("<sfile>:p")
silent only
silent tabonly
cd ~/repos/ai.skillz
if expand('%') == '' && !&modified && line('$') <= 1 && getline(1) == ''
  let s:wipebuf = bufnr('%')
endif
let s:shortmess_save = &shortmess
if &shortmess =~ 'A'
  set shortmess=aoOA
else
  set shortmess=aoO
endif
badd +1 plans/claude/init-extraction-plan.md
badd +1 prompts/conf.toml
badd +1 .git/config
badd +1 plans/claude/init-extraction-plan.summary.md
badd +8 templates/commit-msg/style-guide-reference.md.j2
badd +1 templates/commit-msg/conf.toml.j2
badd +1 skills/gish/SKILL.md
badd +11 skills/inter-skill-review/DEPLOY.md
badd +1 skills/py-codestyle/DEPLOY.md
badd +1 skills/py-codestyle/SKILL.md
badd +1 skills/run-tests/references/tractor-example.md
badd +1 templates/run-tests/SKILL.md.j2
badd +1 prompts/init.md
badd +1 py313/CACHEDIR.TAG
badd +15 skills/code-review-changes/DEPLOY.md
badd +2 skills/resolve-conflicts/SKILL.md
badd +1 skills/resolve-conflicts/DEPLOY.md
badd +4 skills/commit-msg/references/piker-SKILL.md
badd +1 skills/commit-msg/ROADMAP.md
badd +0 skills/commit-msg/SKILL.md
argglobal
%argdel
edit skills/commit-msg/SKILL.md
argglobal
balt skills/commit-msg/ROADMAP.md
setlocal foldmethod=marker
setlocal foldexpr=0
setlocal foldmarker={{{,}}}
setlocal foldignore=#
setlocal foldlevel=1
setlocal foldminlines=1
setlocal foldnestmax=20
setlocal foldenable
let s:l = 94 - ((27 * winheight(0) + 27) / 54)
if s:l < 1 | let s:l = 1 | endif
keepjumps exe s:l
normal! zt
keepjumps 94
normal! 06|
tabnext 1
if exists('s:wipebuf') && len(win_findbuf(s:wipebuf)) == 0 && getbufvar(s:wipebuf, '&buftype') isnot# 'terminal'
  silent exe 'bwipe ' . s:wipebuf
endif
unlet! s:wipebuf
set winheight=1 winwidth=20
let &shortmess = s:shortmess_save
let s:sx = expand("<sfile>:p:r")."x.vim"
if filereadable(s:sx)
  exe "source " . fnameescape(s:sx)
endif
let &g:so = s:so_save | let &g:siso = s:siso_save
set hlsearch
let g:this_session = v:this_session
let g:this_obsession = v:this_session
doautoall SessionLoadPost
unlet SessionLoad
" vim: set ft=vim :
