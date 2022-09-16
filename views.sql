drop view if exists dm_scorecard_ui;
drop view if exists dm_scorecard;

create view dm_scorecard as 
select distinct a.compid, max(c.giturl) as git_url,
max(case when (a.filetype='license') then 'Y' else 'N' end) as license,
max(case when (a.filetype='swagger') then 'Y' else 'N' end) as swagger,
max(case when (a.filetype='readme') then 'Y' else 'N' end) as readme,
max(case when (b.name='GitLinesAdded') then CASE WHEN b.value~E'^\\d+$' THEN b.value::integer ELSE 0 END else NULL end) as git_lines_added,
max(case when (b.name='GitLinesDeleted') then CASE WHEN b.value~E'^\\d+$' THEN b.value::integer ELSE 0 END else NULL end) as git_lines_deleted,
max(case when (b.name='GitLinesTotals') then CASE WHEN b.value~E'^\\d+$' THEN b.value::integer ELSE 0 END else NULL end) as git_lines_total,
max(case when (b.name='GitCommitTimestamp') then b.value else NULL end) as git_commit_timestamp,
max(case when (b.name='GitBranch') then b.value else NULL end) as git_branch,
max(case when (b.name='TotalCommittersCnt') then CASE WHEN b.value~E'^\\d+$' THEN b.value::integer ELSE 0 END else NULL end) as total_committers_cnt,
max(case when (b.name='GitCommittersCnt') then CASE WHEN b.value~E'^\\d+$' THEN b.value::integer ELSE 0 END else NULL end) as git_committers_cnt
from dm.dm_textfile a, dm.dm_componentvars b, dm.dm_componentitem c 
where a.compid = b.compid and a.compid = c.compid
group by a.compid;

create view dm_scorecard_ui as
SELECT distinct c.name as "application", b.name as "component", license, readme, swagger, 
COALESCE(round((git_lines_added + git_lines_deleted)/NULLIF(git_lines_total, 0)*100.00,2),100.00)::text  AS lines_changed, 
COALESCE(round((git_committers_cnt)/NULLIF(total_committers_cnt, 0)*100.00,2),0.00)::text  AS committers 
FROM dm.dm_scorecard a, dm.dm_component b, dm.dm_application c, dm.dm_applicationcomponent d 
WHERE a.compid = b.id and c.id = d.appid and d.compid = a.compid and b.status = 'N' and c.status = 'N';
	 