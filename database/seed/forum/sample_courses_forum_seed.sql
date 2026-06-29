START TRANSACTION;

-- ------------------------------------------------------------------
-- Sample courses forum seed
-- Covers Python, Web Development, and Database Systems
-- Import into communication_db
-- ------------------------------------------------------------------

DELETE FROM course_forum_comments
WHERE comment_id IN (
    971001, 971002, 971003, 971004, 971005, 971006, 971007, 971008,
    971009, 971010, 971011, 971012, 971013, 971014, 971015, 971016,
    971017, 971018,
    971101, 971102, 971103, 971104, 971105, 971106, 971107, 971108,
    971109, 971110, 971111, 971112,
    971201, 971202, 971203, 971204, 971205, 971206, 971207, 971208,
    971209, 971210, 971211, 971212
);

DELETE FROM course_forum_posts
WHERE post_id IN (
    970001, 970002, 970003, 970004, 970005, 970006,
    970101, 970102, 970103, 970104,
    970201, 970202, 970203, 970204
);

INSERT INTO course_forum_posts (
    post_id,
    course_id,
    author_user_id,
    author_email,
    author_name,
    post_kind,
    title,
    content,
    metadata_json,
    created_at,
    updated_at
) VALUES
-- Python
(970001, 800901, 3201, 'amy.chen@ad.unsw.edu.au', 'Amy Chen', 'user', 'Which Python version should we use for Module 1?', 'I noticed the lecture uses Python 3 syntax throughout. Is Python 3.11 fine for all exercises, or should we match a specific lab environment version?', JSON_OBJECT('moduleId', 910901, 'moduleTitle', 'Introduction to Python'), '2026-03-03 09:15:00', '2026-03-03 09:15:00'),
(970002, 800901, 3202, 'joshua.lee@ad.unsw.edu.au', 'Joshua Lee', 'user', 'Any good way to remember list vs tuple?', 'I understand the syntax difference, but in practical programming I keep forgetting when a tuple is a better fit than a list. Any rule of thumb that helped you?', JSON_OBJECT('moduleId', 910905, 'moduleTitle', 'Data Structures'), '2026-03-05 14:20:00', '2026-03-05 14:20:00'),
(970003, 800901, 3203, 'nina.wong@ad.unsw.edu.au', 'Nina Wong', 'user', 'For loop vs while loop in beginner exercises', 'In Module 3 I can often solve the same problem with either a `for` loop or a `while` loop. Is there a style preference we should follow in quizzes or assignments?', JSON_OBJECT('moduleId', 910903, 'moduleTitle', 'Control Structures'), '2026-03-07 11:05:00', '2026-03-07 11:05:00'),
(970004, 800901, 3204, 'daniel.kim@ad.unsw.edu.au', 'Daniel Kim', 'user', 'When should I return a value instead of printing it?', 'I passed the small examples in Module 4, but I still mix up functions that `return` values and functions that just `print`. How do you decide which one to use?', JSON_OBJECT('moduleId', 910904, 'moduleTitle', 'Functions and Modules'), '2026-03-09 16:40:00', '2026-03-09 16:40:00'),
(970005, 800901, 3205, 'sarah.hassan@ad.unsw.edu.au', 'Sarah Hassan', 'user', 'Handling FileNotFoundError cleanly', 'For the file exercises, are we expected to catch `FileNotFoundError` every time, or only when missing files are part of the expected workflow?', JSON_OBJECT('moduleId', 910906, 'moduleTitle', 'File I/O and Exceptions'), '2026-03-11 10:10:00', '2026-03-11 10:10:00'),
(970006, 800901, 3206, 'liam.evans@ad.unsw.edu.au', 'Liam Evans', 'user', 'Why do methods need self?', 'I get that Python instance methods usually start with `self`, but I still do not have a clear mental model of what it refers to when the method runs.', JSON_OBJECT('moduleId', 910907, 'moduleTitle', 'Object-Oriented Programming'), '2026-03-13 18:25:00', '2026-03-13 18:25:00'),
-- Web
(970101, 801001, 3301, 'ella.martin@ad.unsw.edu.au', 'Ella Martin', 'user', 'Best way to practice semantic HTML?', 'I can reproduce examples from the slides, but when I start a page from scratch I am never sure whether to reach for `section`, `article`, or just plain `div`. Any rule of thumb?', JSON_OBJECT('moduleId', 911001, 'moduleTitle', 'HTML and CSS Basics'), '2026-03-18 10:05:00', '2026-03-18 10:05:00'),
(970102, 801001, 3302, 'owen.clark@ad.unsw.edu.au', 'Owen Clark', 'user', 'When should I use state instead of props?', 'In component exercises I understand that props come from the parent, but I still hesitate when deciding whether something belongs in local state or should stay as a prop.', JSON_OBJECT('moduleId', 911003, 'moduleTitle', 'Frontend Frameworks'), '2026-03-20 13:45:00', '2026-03-20 13:45:00'),
(970103, 801001, 3303, 'sophie.wright@ad.unsw.edu.au', 'Sophie Wright', 'user', 'Session cookies or JWT for beginner projects?', 'For small course projects, is there a recommended approach between server-side sessions and JWT auth, or is the point mainly to understand the trade-offs?', JSON_OBJECT('moduleId', 911006, 'moduleTitle', 'Authentication'), '2026-03-22 09:30:00', '2026-03-22 09:30:00'),
(970104, 801001, 3304, 'aaron.hall@ad.unsw.edu.au', 'Aaron Hall', 'user', 'What counts as deployment for this course?', 'If I can run my app locally in Docker, is that already enough for the deployment module, or are we expected to push to a remote server or cloud platform?', JSON_OBJECT('moduleId', 911007, 'moduleTitle', 'Deployment'), '2026-03-24 17:10:00', '2026-03-24 17:10:00'),
-- Database
(970201, 801101, 3401, 'chloe.baker@ad.unsw.edu.au', 'Chloe Baker', 'user', 'How far should we normalize in assignment schemas?', 'I understand 1NF to 3NF in theory, but in practical designs I am unsure when to stop normalizing and when denormalization becomes reasonable.', JSON_OBJECT('moduleId', 911103, 'moduleTitle', 'Database Design'), '2026-04-17 11:00:00', '2026-04-17 11:00:00'),
(970202, 801101, 3402, 'ryan.scott@ad.unsw.edu.au', 'Ryan Scott', 'user', 'Good intuition for choosing indexes?', 'I know indexes help reads, but I still struggle to predict which columns are actually worth indexing in a realistic schema.', JSON_OBJECT('moduleId', 911106, 'moduleTitle', 'Indexing & Optimization'), '2026-04-19 14:25:00', '2026-04-19 14:25:00'),
(970203, 801101, 3403, 'ava.cook@ad.unsw.edu.au', 'Ava Cook', 'user', 'Data warehouse vs OLTP database', 'Could someone explain the practical difference between a transactional database and a data warehouse without using too much jargon?', JSON_OBJECT('moduleId', 911107, 'moduleTitle', 'Data Warehousing'), '2026-04-21 09:40:00', '2026-04-21 09:40:00'),
(970204, 801101, 3404, 'ben.hughes@ad.unsw.edu.au', 'Ben Hughes', 'user', 'When is NoSQL actually the better choice?', 'A lot of examples make NoSQL sound flexible, but in what real situations is it clearly a better fit than a relational database?', JSON_OBJECT('moduleId', 911105, 'moduleTitle', 'NoSQL Databases'), '2026-04-22 16:20:00', '2026-04-22 16:20:00');

INSERT INTO course_forum_comments (
    comment_id,
    post_id,
    course_id,
    author_user_id,
    author_email,
    author_name,
    root_comment_id,
    reply_to_comment_id,
    comment_kind,
    content,
    metadata_json,
    is_deleted,
    deleted_at,
    created_at,
    updated_at
) VALUES
-- Python
(971001, 970001, 800901, 4101, 'michael.tan@ad.unsw.edu.au', 'Michael Tan', NULL, NULL, 'user', 'Python 3.11 should be completely fine for the topics in Module 1. The important part is just to stay on Python 3 rather than Python 2 syntax.', JSON_OBJECT('tag', 'version-advice'), FALSE, NULL, '2026-03-03 10:02:00', '2026-03-03 10:02:00'),
(971002, 970001, 800901, 4102, 'grace.liu@ad.unsw.edu.au', 'Grace Liu', NULL, NULL, 'user', 'If you are following the lecture slides and notes, any recent Python 3 version is okay. I used 3.12 locally and did not hit any issues in the first exercises.', JSON_OBJECT('tag', 'version-advice'), FALSE, NULL, '2026-03-03 10:20:00', '2026-03-03 10:20:00'),
(971003, 970001, 800901, 4103, 'amy.chen@ad.unsw.edu.au', 'Amy Chen', 971001, 971001, 'user', 'That helps a lot, thanks. I mainly wanted to make sure assignment code would not break because of a version mismatch.', JSON_OBJECT('tag', 'follow-up'), FALSE, NULL, '2026-03-03 10:31:00', '2026-03-03 10:31:00'),
(971004, 970002, 800901, 4104, 'olivia.moore@ad.unsw.edu.au', 'Olivia Moore', NULL, NULL, 'user', 'My shortcut is: use a list when I expect the data to change, and a tuple when the values should stay fixed, like coordinates or a pair of settings.', JSON_OBJECT('tag', 'data-structures'), FALSE, NULL, '2026-03-05 15:04:00', '2026-03-05 15:04:00'),
(971005, 970002, 800901, 4105, 'ethan.park@ad.unsw.edu.au', 'Ethan Park', NULL, NULL, 'user', 'Also worth noticing that tuples can be dictionary keys while lists cannot, because tuples are immutable.', JSON_OBJECT('tag', 'data-structures'), FALSE, NULL, '2026-03-05 15:26:00', '2026-03-05 15:26:00'),
(971006, 970003, 800901, 4106, 'isabella.ng@ad.unsw.edu.au', 'Isabella Ng', NULL, NULL, 'user', 'I usually pick `for` when I already know the iterable, and `while` when the loop should keep running until some condition changes over time.', JSON_OBJECT('tag', 'control-structures'), FALSE, NULL, '2026-03-07 11:28:00', '2026-03-07 11:28:00'),
(971007, 970003, 800901, 4107, 'nina.wong@ad.unsw.edu.au', 'Nina Wong', 971006, 971006, 'user', 'That makes sense. So for loops are usually clearer when I am iterating through a list or range directly.', JSON_OBJECT('tag', 'follow-up'), FALSE, NULL, '2026-03-07 11:36:00', '2026-03-07 11:36:00'),
(971008, 970004, 800901, 4108, 'harry.zhang@ad.unsw.edu.au', 'Harry Zhang', NULL, NULL, 'user', 'If another part of your program needs the result, return it. If the goal is only to show something to the user, print might be enough.', JSON_OBJECT('tag', 'functions'), FALSE, NULL, '2026-03-09 17:01:00', '2026-03-09 17:01:00'),
(971009, 970004, 800901, 4109, 'daniel.kim@ad.unsw.edu.au', 'Daniel Kim', 971008, 971008, 'user', 'That is the distinction I was missing. I kept printing inside helper functions even when later code needed the computed value.', JSON_OBJECT('tag', 'follow-up'), FALSE, NULL, '2026-03-09 17:10:00', '2026-03-09 17:10:00'),
(971010, 970005, 800901, 4110, 'mia.roberts@ad.unsw.edu.au', 'Mia Roberts', NULL, NULL, 'user', 'I would handle it when a missing file is a realistic possibility from user input or external data. If the file should always exist, letting it fail loudly can be useful during debugging.', JSON_OBJECT('tag', 'exceptions'), FALSE, NULL, '2026-03-11 10:33:00', '2026-03-11 10:33:00'),
(971011, 970005, 800901, 4111, 'sarah.hassan@ad.unsw.edu.au', 'Sarah Hassan', 971010, 971010, 'user', 'That is a good distinction. I was overusing try/except even in cases where a missing file probably meant I had set up the test incorrectly.', JSON_OBJECT('tag', 'follow-up'), FALSE, NULL, '2026-03-11 10:44:00', '2026-03-11 10:44:00'),
(971012, 970006, 800901, 4112, 'charlotte.green@ad.unsw.edu.au', 'Charlotte Green', NULL, NULL, 'user', 'I think of `self` as “this object”. When you call `student.print_name()`, Python passes that specific `student` instance into the method as `self`.', JSON_OBJECT('tag', 'oop'), FALSE, NULL, '2026-03-13 18:55:00', '2026-03-13 18:55:00'),
(971013, 970006, 800901, 4113, 'liam.evans@ad.unsw.edu.au', 'Liam Evans', 971012, 971012, 'user', 'That phrasing actually helps. I was treating `self` like a magic keyword instead of a reference to the current object.', JSON_OBJECT('tag', 'follow-up'), FALSE, NULL, '2026-03-13 19:02:00', '2026-03-13 19:02:00'),
(971014, 970006, 800901, 4114, 'jack.peterson@ad.unsw.edu.au', 'Jack Peterson', NULL, NULL, 'user', 'One practical way to test your understanding is to print `self` inside a method and compare two different instances. You will see they are different objects with different state.', JSON_OBJECT('tag', 'oop'), FALSE, NULL, '2026-03-13 19:10:00', '2026-03-13 19:10:00'),
(971015, 970002, 800901, 4115, 'joshua.lee@ad.unsw.edu.au', 'Joshua Lee', 971004, 971004, 'user', 'That list-versus-tuple rule of thumb is exactly what I needed. Thank you.', JSON_OBJECT('tag', 'follow-up'), FALSE, NULL, '2026-03-05 15:40:00', '2026-03-05 15:40:00'),
(971016, 970003, 800901, 4116, 'lucas.young@ad.unsw.edu.au', 'Lucas Young', NULL, NULL, 'user', 'In graded work I would optimise for readability first. If a `for` loop makes the intent clearer, that is usually the better beginner choice.', JSON_OBJECT('tag', 'control-structures'), FALSE, NULL, '2026-03-07 11:49:00', '2026-03-07 11:49:00'),
(971017, 970004, 800901, 4117, 'amelia.carter@ad.unsw.edu.au', 'Amelia Carter', NULL, NULL, 'user', 'A quick test is to ask: do I want to use this result later in another expression? If yes, return it. If not, printing may be fine for debugging or user-facing output.', JSON_OBJECT('tag', 'functions'), FALSE, NULL, '2026-03-09 17:18:00', '2026-03-09 17:18:00'),
(971018, 970005, 800901, 4118, 'noah.turner@ad.unsw.edu.au', 'Noah Turner', NULL, NULL, 'user', 'For assignment-style code, I normally catch only the exceptions I can handle meaningfully. Otherwise I let the error propagate so I do not hide a real bug.', JSON_OBJECT('tag', 'exceptions'), FALSE, NULL, '2026-03-11 10:53:00', '2026-03-11 10:53:00'),
-- Web
(971101, 970101, 801001, 4201, 'mia.kelly@ad.unsw.edu.au', 'Mia Kelly', NULL, NULL, 'user', 'I try to ask “does this block have independent meaning?” If yes, I reach for semantic tags like `section` or `article`; if not, a `div` is often enough.', JSON_OBJECT('tag', 'html-css'), FALSE, NULL, '2026-03-18 10:28:00', '2026-03-18 10:28:00'),
(971102, 970101, 801001, 4202, 'ella.martin@ad.unsw.edu.au', 'Ella Martin', 971101, 971101, 'user', 'That is a really practical test. I was overthinking it as if every container needed a semantic element.', JSON_OBJECT('tag', 'follow-up'), FALSE, NULL, '2026-03-18 10:36:00', '2026-03-18 10:36:00'),
(971103, 970102, 801001, 4203, 'noah.james@ad.unsw.edu.au', 'Noah James', NULL, NULL, 'user', 'If the data can change inside the component because of user interaction, local state is usually a good fit. Props are better when the parent already owns the value.', JSON_OBJECT('tag', 'frontend-frameworks'), FALSE, NULL, '2026-03-20 14:03:00', '2026-03-20 14:03:00'),
(971104, 970102, 801001, 4204, 'owen.clark@ad.unsw.edu.au', 'Owen Clark', 971103, 971103, 'user', 'That helps. I think I kept putting temporary UI state in the parent for no reason.', JSON_OBJECT('tag', 'follow-up'), FALSE, NULL, '2026-03-20 14:12:00', '2026-03-20 14:12:00'),
(971105, 970103, 801001, 4205, 'grace.turner@ad.unsw.edu.au', 'Grace Turner', NULL, NULL, 'user', 'For beginner projects I would focus less on which one is “best” and more on understanding the trade-offs clearly. Sessions can feel simpler to reason about at first.', JSON_OBJECT('tag', 'authentication'), FALSE, NULL, '2026-03-22 09:55:00', '2026-03-22 09:55:00'),
(971106, 970103, 801001, 4206, 'sophie.wright@ad.unsw.edu.au', 'Sophie Wright', 971105, 971105, 'user', 'That matches what I was thinking. JWT felt more advanced, but I was not sure whether using sessions would look “too simple”.', JSON_OBJECT('tag', 'follow-up'), FALSE, NULL, '2026-03-22 10:07:00', '2026-03-22 10:07:00'),
(971107, 970104, 801001, 4207, 'liam.brooks@ad.unsw.edu.au', 'Liam Brooks', NULL, NULL, 'user', 'If the module is about deployment, I would expect at least one environment beyond your laptop, even if it is just a simple hosted target or a school server.', JSON_OBJECT('tag', 'deployment'), FALSE, NULL, '2026-03-24 17:31:00', '2026-03-24 17:31:00'),
(971108, 970104, 801001, 4208, 'aaron.hall@ad.unsw.edu.au', 'Aaron Hall', 971107, 971107, 'user', 'That is useful. I will plan for something small but real instead of treating Docker on localhost as the final step.', JSON_OBJECT('tag', 'follow-up'), FALSE, NULL, '2026-03-24 17:42:00', '2026-03-24 17:42:00'),
(971109, 970101, 801001, 4209, 'lucy.price@ad.unsw.edu.au', 'Lucy Price', NULL, NULL, 'user', 'I also found browser devtools helpful because the HTML outline makes it easier to see whether the structure still makes sense.', JSON_OBJECT('tag', 'html-css'), FALSE, NULL, '2026-03-18 10:48:00', '2026-03-18 10:48:00'),
(971110, 970102, 801001, 4210, 'harry.foster@ad.unsw.edu.au', 'Harry Foster', NULL, NULL, 'user', 'A good smell is when multiple sibling components need the same value. That is often a sign the state should move up.', JSON_OBJECT('tag', 'frontend-frameworks'), FALSE, NULL, '2026-03-20 14:19:00', '2026-03-20 14:19:00'),
(971111, 970103, 801001, 4211, 'amelia.ward@ad.unsw.edu.au', 'Amelia Ward', NULL, NULL, 'user', 'If you store everything in the token too early, debugging can get harder. Sessions feel more concrete when you are first learning auth flows.', JSON_OBJECT('tag', 'authentication'), FALSE, NULL, '2026-03-22 10:14:00', '2026-03-22 10:14:00'),
(971112, 970104, 801001, 4212, 'jack.morris@ad.unsw.edu.au', 'Jack Morris', NULL, NULL, 'user', 'I think deployment is also about understanding environment variables, logging, and failure modes, not just “can I start the app”.', JSON_OBJECT('tag', 'deployment'), FALSE, NULL, '2026-03-24 17:49:00', '2026-03-24 17:49:00'),
-- Database
(971201, 970201, 801101, 4301, 'sophie.hill@ad.unsw.edu.au', 'Sophie Hill', NULL, NULL, 'user', 'I usually normalize until the design is clean and then only denormalize when I have a concrete performance or reporting reason.', JSON_OBJECT('tag', 'database-design'), FALSE, NULL, '2026-04-17 11:24:00', '2026-04-17 11:24:00'),
(971202, 970201, 801101, 4302, 'chloe.baker@ad.unsw.edu.au', 'Chloe Baker', 971201, 971201, 'user', 'That framing helps. I was treating denormalization as something that had to happen eventually rather than something justified by a specific need.', JSON_OBJECT('tag', 'follow-up'), FALSE, NULL, '2026-04-17 11:35:00', '2026-04-17 11:35:00'),
(971203, 970202, 801101, 4303, 'ethan.reed@ad.unsw.edu.au', 'Ethan Reed', NULL, NULL, 'user', 'I start by looking at the columns used in `WHERE`, joins, and ordering. If those patterns happen often, that is where indexes are most likely to help.', JSON_OBJECT('tag', 'optimization'), FALSE, NULL, '2026-04-19 14:47:00', '2026-04-19 14:47:00'),
(971204, 970202, 801101, 4304, 'ryan.scott@ad.unsw.edu.au', 'Ryan Scott', 971203, 971203, 'user', 'That gives me a much better mental model than “index everything important”.', JSON_OBJECT('tag', 'follow-up'), FALSE, NULL, '2026-04-19 14:55:00', '2026-04-19 14:55:00'),
(971205, 970203, 801101, 4305, 'isla.wood@ad.unsw.edu.au', 'Isla Wood', NULL, NULL, 'user', 'I think of OLTP as optimized for many small operational transactions, while a warehouse is optimized for large analytical queries across historical data.', JSON_OBJECT('tag', 'warehousing'), FALSE, NULL, '2026-04-21 10:01:00', '2026-04-21 10:01:00'),
(971206, 970203, 801101, 4306, 'ava.cook@ad.unsw.edu.au', 'Ava Cook', 971205, 971205, 'user', 'That explanation is much clearer than the textbook wording I was stuck on.', JSON_OBJECT('tag', 'follow-up'), FALSE, NULL, '2026-04-21 10:12:00', '2026-04-21 10:12:00'),
(971207, 970204, 801101, 4307, 'oliver.bell@ad.unsw.edu.au', 'Oliver Bell', NULL, NULL, 'user', 'If your data shape changes a lot or you naturally store document-style records, NoSQL can feel more natural. It is not automatically better, just a different trade-off.', JSON_OBJECT('tag', 'nosql'), FALSE, NULL, '2026-04-22 16:39:00', '2026-04-22 16:39:00'),
(971208, 970204, 801101, 4308, 'ben.hughes@ad.unsw.edu.au', 'Ben Hughes', 971207, 971207, 'user', 'That makes sense. I think I was searching for a universal rule when it is really about workload and model fit.', JSON_OBJECT('tag', 'follow-up'), FALSE, NULL, '2026-04-22 16:48:00', '2026-04-22 16:48:00'),
(971209, 970201, 801101, 4309, 'mia.white@ad.unsw.edu.au', 'Mia White', NULL, NULL, 'user', 'In assignments I would probably mention where denormalization could help later, but keep the main schema clean first.', JSON_OBJECT('tag', 'database-design'), FALSE, NULL, '2026-04-17 11:42:00', '2026-04-17 11:42:00'),
(971210, 970202, 801101, 4310, 'leo.gray@ad.unsw.edu.au', 'Leo Gray', NULL, NULL, 'user', 'Execution plans are really helpful once you know the query pattern you are optimizing for.', JSON_OBJECT('tag', 'optimization'), FALSE, NULL, '2026-04-19 15:02:00', '2026-04-19 15:02:00'),
(971211, 970203, 801101, 4311, 'zoe.long@ad.unsw.edu.au', 'Zoe Long', NULL, NULL, 'user', 'Warehouses also tend to denormalize dimensions more because analytical readability matters a lot.', JSON_OBJECT('tag', 'warehousing'), FALSE, NULL, '2026-04-21 10:18:00', '2026-04-21 10:18:00'),
(971212, 970204, 801101, 4312, 'noah.powell@ad.unsw.edu.au', 'Noah Powell', NULL, NULL, 'user', 'A nice way to think about it is that NoSQL often makes some data access patterns simpler, but you pay for that with different consistency and querying trade-offs.', JSON_OBJECT('tag', 'nosql'), FALSE, NULL, '2026-04-22 16:57:00', '2026-04-22 16:57:00');

COMMIT;
