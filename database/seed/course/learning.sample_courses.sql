START TRANSACTION;

-- Clean existing sample data in dependency order.
DELETE FROM module_materials
WHERE module_id IN (
    910901, 910902, 910903, 910904, 910905, 910906, 910907,
    911001, 911002, 911003, 911004, 911005, 911006, 911007,
    911101, 911102, 911103, 911104, 911105, 911106, 911107
);

DELETE FROM modules
WHERE module_id IN (
    910901, 910902, 910903, 910904, 910905, 910906, 910907,
    911001, 911002, 911003, 911004, 911005, 911006, 911007,
    911101, 911102, 911103, 911104, 911105, 911106, 911107
);

DELETE FROM learning_paths
WHERE learning_path_id IN (900901, 901001, 901101);

DELETE FROM courses
WHERE course_id IN (800901, 801001, 801101);

-- ------------------------------------------------------------------
-- Course 1: Python Programming
-- ------------------------------------------------------------------
INSERT INTO courses (
    course_id,
    educator_id,
    title,
    subtitle,
    description,
    cover_image_url,
    status,
    difficulty_level,
    estimated_minutes,
    category,
    language_code,
    is_public,
    published_at
) VALUES (
    800901,
    2101,
    'PYPROG101 - Python Programming - 2026',
    'Python Basic Programming',
    'Learn Python fundamentals, data structures, files, exceptions, and object-oriented programming through structured lecture materials.',
    NULL,
    'published',
    'beginner',
    720,
    'Programming',
    'en',
    TRUE,
    '2026-02-01 09:00:00'
);

INSERT INTO learning_paths (
    learning_path_id,
    course_id,
    title,
    description
) VALUES (
    900901,
    800901,
    'Python Programming Learning Path',
    'Start from core Python syntax and progress toward practical programming, abstraction, and object-oriented design.'
);

INSERT INTO modules (
    module_id,
    learning_path_id,
    title,
    description,
    content,
    sort_order,
    estimated_minutes,
    status
) VALUES
(
    910901,
    900901,
    'Introduction to Python',
    'Python basics, setup, execution model, and first programs.',
    'Covers the Python programming environment, basic syntax, running programs, and writing first scripts.',
    1,
    60,
    'published'
),
(
    910902,
    900901,
    'Data Types and Variables',
    'Strings, numbers, booleans, variables, and simple expressions.',
    'Introduces Python data types, variables, assignment, expressions, and common beginner programming patterns.',
    2,
    90,
    'published'
),
(
    910903,
    900901,
    'Control Structures',
    'Conditional logic, loops, and flow control.',
    'Focuses on branching, iteration, boolean logic, and patterns for controlling program execution.',
    3,
    90,
    'published'
),
(
    910904,
    900901,
    'Functions and Modules',
    'Functions, decomposition, abstraction, and reusable modules.',
    'Shows how to define functions, organize code, import modules, and write reusable program components.',
    4,
    90,
    'published'
),
(
    910905,
    900901,
    'Data Structures',
    'Lists, tuples, dictionaries, sets, and mutability.',
    'Develops fluency with Python collections and how they support common algorithmic tasks.',
    5,
    90,
    'published'
),
(
    910906,
    900901,
    'File I/O and Exceptions',
    'Reading and writing files, exceptions, and defensive programming.',
    'Covers file-based workflows, debugging, exception handling, and robust program behavior.',
    6,
    90,
    'published'
),
(
    910907,
    900901,
    'Object-Oriented Programming',
    'Classes, objects, methods, and program design with abstraction.',
    'Introduces classes, objects, encapsulation, and object-oriented design patterns in Python.',
    7,
    120,
    'published'
);

INSERT INTO module_materials (
    material_id,
    module_id,
    title,
    material_type,
    resource_url,
    sort_order,
    metadata_json
) VALUES
(
    930001,
    910901,
    'Introduction to Python Lecture Video',
    'video',
    'materials/python/module_01/python_01_introduction.mp4',
    1,
    JSON_OBJECT('source', 'local', 'category', 'lecture-video')
),
(
    930002,
    910901,
    'Introduction to Python Lecture Notes',
    'pdf',
    'materials/python/module_01/python_01_introduction.pdf',
    2,
    JSON_OBJECT('source', 'local', 'category', 'lecture-pdf')
),
(
    930003,
    910901,
    'Introduction to Python Supplementary Notes',
    'file',
    'materials/python/module_01/python_01_introduction_notes.pdf',
    3,
    JSON_OBJECT('source', 'local', 'category', 'notes')
),
(
    930004,
    910902,
    'Data Types and Variables Lecture Video',
    'video',
    'materials/python/module_02/python_02_data_types_variables.mp4',
    1,
    JSON_OBJECT('source', 'local', 'category', 'lecture-video')
),
(
    930005,
    910902,
    'Data Types and Variables Lecture Notes',
    'pdf',
    'materials/python/module_02/python_02_data_types_variables.pdf',
    2,
    JSON_OBJECT('source', 'local', 'category', 'lecture-pdf')
),
(
    930006,
    910902,
    'Data Types and Variables Supplementary Notes',
    'file',
    'materials/python/module_02/python_02_data_types_variables_notes.pdf',
    3,
    JSON_OBJECT('source', 'local', 'category', 'notes')
),
(
    930007,
    910903,
    'Control Structures Lecture Video',
    'video',
    'materials/python/module_03/python_03_control_structures.mp4',
    1,
    JSON_OBJECT('source', 'local', 'category', 'lecture-video')
),
(
    930008,
    910903,
    'Control Structures Lecture Notes',
    'pdf',
    'materials/python/module_03/python_03_control_structures.pdf',
    2,
    JSON_OBJECT('source', 'local', 'category', 'lecture-pdf')
),
(
    930009,
    910903,
    'Control Structures Supplementary Notes',
    'file',
    'materials/python/module_03/python_03_control_structures_notes.pdf',
    3,
    JSON_OBJECT('source', 'local', 'category', 'notes')
),
(
    930010,
    910904,
    'Functions and Modules Lecture Video',
    'video',
    'materials/python/module_04/python_04_functions_modules.mp4',
    1,
    JSON_OBJECT('source', 'local', 'category', 'lecture-video')
),
(
    930011,
    910904,
    'Functions and Modules Lecture Notes',
    'pdf',
    'materials/python/module_04/python_04_functions_modules.pdf',
    2,
    JSON_OBJECT('source', 'local', 'category', 'lecture-pdf')
),
(
    930012,
    910904,
    'Functions and Modules Supplementary Notes',
    'file',
    'materials/python/module_04/python_04_functions_modules_notes.pdf',
    3,
    JSON_OBJECT('source', 'local', 'category', 'notes')
),
(
    930013,
    910905,
    'Data Structures Lecture Video',
    'video',
    'materials/python/module_05/python_05_data_structures.mp4',
    1,
    JSON_OBJECT('source', 'local', 'category', 'lecture-video')
),
(
    930014,
    910905,
    'Data Structures Lecture Notes',
    'pdf',
    'materials/python/module_05/python_05_data_structures.pdf',
    2,
    JSON_OBJECT('source', 'local', 'category', 'lecture-pdf')
),
(
    930015,
    910905,
    'Data Structures Supplementary Notes',
    'file',
    'materials/python/module_05/python_05_data_structures_notes.pdf',
    3,
    JSON_OBJECT('source', 'local', 'category', 'notes')
),
(
    930016,
    910906,
    'File I/O and Exceptions Lecture Video',
    'video',
    'materials/python/module_06/python_06_file_io_exceptions.mp4',
    1,
    JSON_OBJECT('source', 'local', 'category', 'lecture-video')
),
(
    930017,
    910906,
    'File I/O and Exceptions Lecture Notes',
    'pdf',
    'materials/python/module_06/python_06_file_io_exceptions.pdf',
    2,
    JSON_OBJECT('source', 'local', 'category', 'lecture-pdf')
),
(
    930018,
    910906,
    'File I/O and Exceptions Supplementary Notes',
    'file',
    'materials/python/module_06/python_06_file_io_exceptions_notes.pdf',
    3,
    JSON_OBJECT('source', 'local', 'category', 'notes')
),
(
    930019,
    910907,
    'Object-Oriented Programming Lecture Video',
    'video',
    'materials/python/module_07/python_07_oop.mp4',
    1,
    JSON_OBJECT('source', 'local', 'category', 'lecture-video')
),
(
    930020,
    910907,
    'Object-Oriented Programming Lecture Notes',
    'pdf',
    'materials/python/module_07/python_07_oop.pdf',
    2,
    JSON_OBJECT('source', 'local', 'category', 'lecture-pdf')
),
(
    930021,
    910907,
    'Object-Oriented Programming Supplementary Notes',
    'file',
    'materials/python/module_07/python_07_oop_notes.pdf',
    3,
    JSON_OBJECT('source', 'local', 'category', 'notes')
);

-- ------------------------------------------------------------------
-- Course 2: Web Development
-- ------------------------------------------------------------------
INSERT INTO courses (
    course_id,
    educator_id,
    title,
    subtitle,
    description,
    cover_image_url,
    status,
    difficulty_level,
    estimated_minutes,
    category,
    language_code,
    is_public,
    published_at
) VALUES (
    801001,
    2102,
    'WEBDEV201 - Web Development - 2026',
    'Full-Stack Frontend and Backend Development',
    'Build modern web applications with HTML, CSS, JavaScript, frontend frameworks, backend patterns, databases, authentication, and deployment.',
    NULL,
    'published',
    'intermediate',
    840,
    'Web Development',
    'en',
    TRUE,
    '2026-03-10 09:00:00'
);

INSERT INTO learning_paths (
    learning_path_id,
    course_id,
    title,
    description
) VALUES (
    901001,
    801001,
    'Web Development Learning Path',
    'Move from core web page construction through client interaction, backend logic, persistence, security, and deployment.'
);

INSERT INTO modules (
    module_id,
    learning_path_id,
    title,
    description,
    content,
    sort_order,
    estimated_minutes,
    status
) VALUES
(
    911001,
    901001,
    'HTML and CSS Basics',
    'Markup, styling, layout, and responsive design foundations.',
    'Introduces semantic HTML, CSS styling, layout systems, and the principles of building readable web pages.',
    1,
    70,
    'published'
),
(
    911002,
    901001,
    'JavaScript Fundamentals',
    'Variables, functions, browser logic, and the DOM.',
    'Builds core JavaScript fluency for browser programming, event handling, and DOM updates.',
    2,
    90,
    'published'
),
(
    911003,
    901001,
    'Frontend Frameworks',
    'Components, state, and application structure in frontend frameworks.',
    'Explores component-based UI development and the patterns used in framework-based frontend applications.',
    3,
    90,
    'published'
),
(
    911004,
    901001,
    'Backend with Node.js',
    'Server-side request handling, routing, and application structure.',
    'Introduces backend application architecture, request lifecycle, routing, and server-side programming workflows.',
    4,
    90,
    'published'
),
(
    911005,
    901001,
    'Databases for Web',
    'Integrating persistence and data models into web applications.',
    'Shows how web applications store, query, and manage data with database-backed workflows.',
    5,
    90,
    'published'
),
(
    911006,
    901001,
    'Authentication',
    'Sessions, identity, user access, and secure login flows.',
    'Focuses on user authentication, session handling, and safe patterns for account-protected applications.',
    6,
    90,
    'published'
),
(
    911007,
    901001,
    'Deployment',
    'Delivery, scaling, and operating web systems in production.',
    'Covers shipping web applications, operating them reliably, and understanding production deployment concerns.',
    7,
    90,
    'published'
);

INSERT INTO module_materials (
    material_id,
    module_id,
    title,
    material_type,
    resource_url,
    sort_order,
    metadata_json
) VALUES
(
    930101,
    911001,
    'HTML and CSS Basics Lecture Video',
    'video',
    'materials/web/module_01/web_01_html_css.mp4',
    1,
    JSON_OBJECT('source', 'local', 'category', 'lecture-video')
),
(
    930102,
    911001,
    'HTML and CSS Basics Lecture Notes',
    'pdf',
    'materials/web/module_01/web_01_html_css.pdf',
    2,
    JSON_OBJECT('source', 'local', 'category', 'lecture-pdf')
),
(
    930103,
    911001,
    'HTML and CSS Basics Supplementary Notes',
    'file',
    'materials/web/module_01/web_01_html_css_notes.pdf',
    3,
    JSON_OBJECT('source', 'local', 'category', 'notes')
),
(
    930104,
    911002,
    'JavaScript Fundamentals Lecture Video',
    'video',
    'materials/web/module_02/web_02_javascript.mp4',
    1,
    JSON_OBJECT('source', 'local', 'category', 'lecture-video')
),
(
    930105,
    911002,
    'JavaScript Fundamentals Lecture Notes',
    'pdf',
    'materials/web/module_02/web_02_javascript.pdf',
    2,
    JSON_OBJECT('source', 'local', 'category', 'lecture-pdf')
),
(
    930106,
    911002,
    'JavaScript Fundamentals Supplementary Notes',
    'file',
    'materials/web/module_02/web_02_javascript_notes.pdf',
    3,
    JSON_OBJECT('source', 'local', 'category', 'notes')
),
(
    930107,
    911003,
    'Frontend Frameworks Lecture Video',
    'video',
    'materials/web/module_03/web_03_frontend_frameworks.mp4',
    1,
    JSON_OBJECT('source', 'local', 'category', 'lecture-video')
),
(
    930108,
    911003,
    'Frontend Frameworks Lecture Notes',
    'pdf',
    'materials/web/module_03/web_03_frontend_frameworks.pdf',
    2,
    JSON_OBJECT('source', 'local', 'category', 'lecture-pdf')
),
(
    930109,
    911003,
    'Frontend Frameworks Supplementary Notes',
    'file',
    'materials/web/module_03/web_03_frontend_frameworks_notes.pdf',
    3,
    JSON_OBJECT('source', 'local', 'category', 'notes')
),
(
    930110,
    911004,
    'Backend with Node.js Lecture Video',
    'video',
    'materials/web/module_04/web_04_backend.mp4',
    1,
    JSON_OBJECT('source', 'local', 'category', 'lecture-video')
),
(
    930111,
    911004,
    'Backend with Node.js Lecture Notes',
    'pdf',
    'materials/web/module_04/web_04_backend.pdf',
    2,
    JSON_OBJECT('source', 'local', 'category', 'lecture-pdf')
),
(
    930112,
    911004,
    'Backend with Node.js Supplementary Notes',
    'file',
    'materials/web/module_04/web_04_backend_notes.pdf',
    3,
    JSON_OBJECT('source', 'local', 'category', 'notes')
),
(
    930113,
    911005,
    'Databases for Web Lecture Video',
    'video',
    'materials/web/module_05/web_05_databases_for_web.mp4',
    1,
    JSON_OBJECT('source', 'local', 'category', 'lecture-video')
),
(
    930114,
    911005,
    'Databases for Web Lecture Notes',
    'pdf',
    'materials/web/module_05/web_05_databases_for_web.pdf',
    2,
    JSON_OBJECT('source', 'local', 'category', 'lecture-pdf')
),
(
    930115,
    911005,
    'Databases for Web Supplementary Notes',
    'file',
    'materials/web/module_05/web_05_databases_for_web_notes.pdf',
    3,
    JSON_OBJECT('source', 'local', 'category', 'notes')
),
(
    930116,
    911006,
    'Authentication Lecture Video',
    'video',
    'materials/web/module_06/web_06_authentication.mp4',
    1,
    JSON_OBJECT('source', 'local', 'category', 'lecture-video')
),
(
    930117,
    911006,
    'Authentication Lecture Notes',
    'pdf',
    'materials/web/module_06/web_06_authentication.pdf',
    2,
    JSON_OBJECT('source', 'local', 'category', 'lecture-pdf')
),
(
    930118,
    911006,
    'Authentication Supplementary Notes',
    'file',
    'materials/web/module_06/web_06_authentication_notes.pdf',
    3,
    JSON_OBJECT('source', 'local', 'category', 'notes')
),
(
    930119,
    911007,
    'Deployment Lecture Video',
    'video',
    'materials/web/module_07/web_07_deployment.mp4',
    1,
    JSON_OBJECT('source', 'local', 'category', 'lecture-video')
),
(
    930120,
    911007,
    'Deployment Lecture Notes',
    'pdf',
    'materials/web/module_07/web_07_deployment.pdf',
    2,
    JSON_OBJECT('source', 'local', 'category', 'lecture-pdf')
),
(
    930121,
    911007,
    'Deployment Supplementary Notes',
    'file',
    'materials/web/module_07/web_07_deployment_notes.pdf',
    3,
    JSON_OBJECT('source', 'local', 'category', 'notes')
);

-- ------------------------------------------------------------------
-- Course 3: Database Systems
-- ------------------------------------------------------------------
INSERT INTO courses (
    course_id,
    educator_id,
    title,
    subtitle,
    description,
    cover_image_url,
    status,
    difficulty_level,
    estimated_minutes,
    category,
    language_code,
    is_public,
    published_at
) VALUES (
    801101,
    2103,
    'DBSYS301 - Database - 2026',
    'Database Design and Management',
    'Study database fundamentals, SQL, design, optimization, NoSQL systems, and warehouse-oriented analytical concepts.',
    NULL,
    'published',
    'intermediate',
    820,
    'Database',
    'en',
    TRUE,
    '2026-04-15 09:00:00'
);

INSERT INTO learning_paths (
    learning_path_id,
    course_id,
    title,
    description
) VALUES (
    901101,
    801101,
    'Database Learning Path',
    'Build database knowledge from core models and SQL to optimization, scaling, and analytical systems.'
);

INSERT INTO modules (
    module_id,
    learning_path_id,
    title,
    description,
    content,
    sort_order,
    estimated_minutes,
    status
) VALUES
(
    911101,
    901101,
    'Database Concepts',
    'Relational thinking, transactions, and the fundamentals of persistent data systems.',
    'Introduces core database ideas including relations, consistency, constraints, and why structured data systems matter.',
    1,
    60,
    'published'
),
(
    911102,
    901101,
    'SQL Fundamentals',
    'Queries, filtering, joining, and data manipulation.',
    'Develops working SQL fluency with core query constructs and data manipulation patterns.',
    2,
    100,
    'published'
),
(
    911103,
    901101,
    'Database Design',
    'Schema design, relationships, and modeling structured data.',
    'Covers schema design tradeoffs, normalization concepts, and modeling application data cleanly.',
    3,
    90,
    'published'
),
(
    911104,
    901101,
    'Advanced SQL',
    'Aggregations, advanced querying patterns, and analytical SQL.',
    'Explores advanced SQL constructs used for reporting, summarization, and richer database workflows.',
    4,
    100,
    'published'
),
(
    911105,
    901101,
    'NoSQL Databases',
    'Alternative data models, flexible schemas, and non-relational systems.',
    'Introduces NoSQL concepts and how non-relational stores support different scalability and data-model needs.',
    5,
    90,
    'published'
),
(
    911106,
    901101,
    'Indexing & Optimization',
    'Indexes, access patterns, and performance-aware querying.',
    'Focuses on query performance, indexing strategy, and reading execution behavior to improve systems.',
    6,
    100,
    'published'
),
(
    911107,
    901101,
    'Data Warehousing',
    'Analytical data organization, warehousing, and large-scale reporting concepts.',
    'Introduces warehouse-oriented thinking, analytics-driven storage, and broader reporting architectures.',
    7,
    120,
    'published'
);

INSERT INTO module_materials (
    material_id,
    module_id,
    title,
    material_type,
    resource_url,
    sort_order,
    metadata_json
) VALUES
(
    930201,
    911101,
    'Database Concepts Lecture Video',
    'video',
    'materials/database/module_01/db_01_database_concepts.mp4',
    1,
    JSON_OBJECT('source', 'local', 'category', 'lecture-video')
),
(
    930202,
    911101,
    'Database Concepts Lecture Notes',
    'pdf',
    'materials/database/module_01/db_01_database_concepts.pdf',
    2,
    JSON_OBJECT('source', 'local', 'category', 'lecture-pdf')
),
(
    930203,
    911101,
    'Database Concepts Supplementary Notes',
    'file',
    'materials/database/module_01/db_01_database_concepts_notes.pdf',
    3,
    JSON_OBJECT('source', 'local', 'category', 'notes')
),
(
    930204,
    911102,
    'SQL Fundamentals Lecture Video',
    'video',
    'materials/database/module_02/db_02_sql_fundamentals.mp4',
    1,
    JSON_OBJECT('source', 'local', 'category', 'lecture-video')
),
(
    930205,
    911102,
    'SQL Fundamentals Lecture Notes',
    'pdf',
    'materials/database/module_02/db_02_sql_fundamentals.pdf',
    2,
    JSON_OBJECT('source', 'local', 'category', 'lecture-pdf')
),
(
    930206,
    911102,
    'SQL Fundamentals Supplementary Notes',
    'file',
    'materials/database/module_02/db_02_sql_fundamentals_notes.pdf',
    3,
    JSON_OBJECT('source', 'local', 'category', 'notes')
),
(
    930207,
    911103,
    'Database Design Lecture Video',
    'video',
    'materials/database/module_03/db_03_database_design.mp4',
    1,
    JSON_OBJECT('source', 'local', 'category', 'lecture-video')
),
(
    930208,
    911103,
    'Database Design Lecture Notes',
    'pdf',
    'materials/database/module_03/db_03_database_design.pdf',
    2,
    JSON_OBJECT('source', 'local', 'category', 'lecture-pdf')
),
(
    930209,
    911103,
    'Database Design Supplementary Notes',
    'file',
    'materials/database/module_03/db_03_database_design_notes.pdf',
    3,
    JSON_OBJECT('source', 'local', 'category', 'notes')
),
(
    930210,
    911104,
    'Advanced SQL Lecture Video',
    'video',
    'materials/database/module_04/db_04_advanced_sql.mp4',
    1,
    JSON_OBJECT('source', 'local', 'category', 'lecture-video')
),
(
    930211,
    911104,
    'Advanced SQL Lecture Notes',
    'pdf',
    'materials/database/module_04/db_04_advanced_sql.pdf',
    2,
    JSON_OBJECT('source', 'local', 'category', 'lecture-pdf')
),
(
    930212,
    911104,
    'Advanced SQL Supplementary Notes',
    'file',
    'materials/database/module_04/db_04_advanced_sql_notes.pdf',
    3,
    JSON_OBJECT('source', 'local', 'category', 'notes')
),
(
    930213,
    911105,
    'NoSQL Databases Lecture Video',
    'video',
    'materials/database/module_05/db_05_nosql_databases.mp4',
    1,
    JSON_OBJECT('source', 'local', 'category', 'lecture-video')
),
(
    930214,
    911105,
    'NoSQL Databases Lecture Notes',
    'pdf',
    'materials/database/module_05/db_05_nosql_databases.pdf',
    2,
    JSON_OBJECT('source', 'local', 'category', 'lecture-pdf')
),
(
    930215,
    911105,
    'NoSQL Databases Supplementary Notes',
    'file',
    'materials/database/module_05/db_05_nosql_databases_notes.pdf',
    3,
    JSON_OBJECT('source', 'local', 'category', 'notes')
),
(
    930216,
    911106,
    'Indexing & Optimization Lecture Video',
    'video',
    'materials/database/module_06/db_06_indexing_optimization.mp4',
    1,
    JSON_OBJECT('source', 'local', 'category', 'lecture-video')
),
(
    930217,
    911106,
    'Indexing & Optimization Lecture Notes',
    'pdf',
    'materials/database/module_06/db_06_indexing_optimization.pdf',
    2,
    JSON_OBJECT('source', 'local', 'category', 'lecture-pdf')
),
(
    930218,
    911106,
    'Indexing & Optimization Supplementary Notes',
    'file',
    'materials/database/module_06/db_06_indexing_optimization_notes.pdf',
    3,
    JSON_OBJECT('source', 'local', 'category', 'notes')
),
(
    930219,
    911107,
    'Data Warehousing Lecture Video',
    'video',
    'materials/database/module_07/db_07_data_warehousing.mp4',
    1,
    JSON_OBJECT('source', 'local', 'category', 'lecture-video')
),
(
    930220,
    911107,
    'Data Warehousing Lecture Notes',
    'pdf',
    'materials/database/module_07/db_07_data_warehousing.pdf',
    2,
    JSON_OBJECT('source', 'local', 'category', 'lecture-pdf')
),
(
    930221,
    911107,
    'Data Warehousing Supplementary Notes',
    'file',
    'materials/database/module_07/db_07_data_warehousing_notes.pdf',
    3,
    JSON_OBJECT('source', 'local', 'category', 'notes')
);

COMMIT;
