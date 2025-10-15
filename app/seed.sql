PRAGMA foreign_keys=ON;

-- Demo student for dashboards/tests
INSERT OR IGNORE INTO student (student_id, name, email, program, password_hash) VALUES
(1, 'Demo Student', 'test@example.com', 'Computer Science', 'scrypt:32768:8:1$Bfg5AHCcWPR0MbIG$a60fa108b4e21585ed24fcd403a80b49c140ea9a1b64618abed649cba66276497d06090f81518f6b535788e975f707f8ee9dfeec6b3caba556cef82b6d5ff484');

INSERT OR IGNORE INTO student_mastery (student_id, concept_tag, mastered, updated_at) VALUES
(1, 'Functional Dependency', 1, datetime('now', '-7 day')),
(1, 'Atomic Values', 1, datetime('now', '-7 day')),
(1, 'Partial Dependency', 0, datetime('now', '-3 day')),
(1, 'Transitive Dependency', 0, datetime('now', '-3 day'));

-- Modules per concept tag
INSERT INTO module (title, description, nf_level, concept_tag, resource_url) VALUES
('Functional Dependencies 101', 'Understand determinants and implied attributes', 'FD', 'Functional Dependency', 'https://en.wikipedia.org/wiki/Functional_dependency'),
('First Normal Form (1NF)', 'Atomic values, no repeating groups', '1NF', 'Atomic Values', 'https://en.wikipedia.org/wiki/First_normal_form'),
('Second Normal Form (2NF)', 'Eliminate partial dependencies', '2NF', 'Partial Dependency', 'https://en.wikipedia.org/wiki/Second_normal_form'),
('Third Normal Form (3NF)', 'Eliminate transitive dependencies', '3NF', 'Transitive Dependency', 'https://en.wikipedia.org/wiki/Third_normal_form');

-- Helper for generating sample questions; options_text: JSON array of 4 strings
-- At least 12 per NF level: FD, 1NF, 2NF, 3NF

-- FD (Functional Dependency)
INSERT INTO quiz (question, options_text, correct_answer, nf_level, concept_tag, explanation, two_category) VALUES
('In relation Orders(OrderID, CustomerID, OrderDate), which FD holds?', '["OrderID -> CustomerID, OrderDate","CustomerID -> OrderID","OrderDate -> OrderID","CustomerID, OrderDate -> OrderID"]', 'OrderID -> CustomerID, OrderDate', 'FD', 'Functional Dependency', 'Primary key determines other attributes.', 'Data Modeling & DBMS Fundamentals'),
('Which best defines a functional dependency?', '["One attribute uniquely determines another","All attributes are atomic","No partial key dependencies","No transitive dependencies"]', 'One attribute uniquely determines another', 'FD', 'Functional Dependency', 'FD defines unique determination.', 'Data Modeling & DBMS Fundamentals'),
('Given A -> B and B -> C, which holds?', '["A -> C","C -> A","A -> B is transitive","No dependency"]', 'A -> C', 'FD', 'Functional Dependency', 'Transitivity of FDs.', 'Data Modeling & DBMS Fundamentals'),
('What is a candidate key?', '["Minimal set determining all attributes","Any non-key attribute","Foreign key","Superkey with redundancy"]', 'Minimal set determining all attributes', 'FD', 'Functional Dependency', 'Candidate key minimality.', 'Data Modeling & DBMS Fundamentals'),
('If AB is a key, which is true?', '["AB -> all attributes","A -> all attributes","B -> all attributes","None"]', 'AB -> all attributes', 'FD', 'Functional Dependency', 'Key determines all attributes.', 'Data Modeling & DBMS Fundamentals'),
('Which violates FD theory?', '["Two rows share key but differ in non-key","Surrogate key used","Nulls in nullable columns","Composite keys used"]', 'Two rows share key but differ in non-key', 'FD', 'Functional Dependency', 'FD violation when non-key differs for same key.', 'Data Modeling & DBMS Fundamentals'),
('Armstrong axioms include?', '["Reflexivity, Augmentation, Transitivity","Commutativity, Distributivity","Normalization, Denormalization","BCNF, 4NF"]', 'Reflexivity, Augmentation, Transitivity', 'FD', 'Functional Dependency', 'Classical axioms.', 'Data Modeling & DBMS Fundamentals'),
('Closure of attribute set is?', '["All attributes determined by it","Only keys","Only FDs","All non-keys"]', 'All attributes determined by it', 'FD', 'Functional Dependency', 'Attribute closure.', 'Data Modeling & DBMS Fundamentals'),
('Which is always true?', '["Key -> every attribute","Non-key -> key","Date -> ID","City -> Country always"]', 'Key -> every attribute', 'FD', 'Functional Dependency', 'Definition of key.', 'Data Modeling & DBMS Fundamentals'),
('BCNF requires?', '["Every determinant is a key","No nulls","Single-attribute keys only","No foreign keys"]', 'Every determinant is a key', 'FD', 'Functional Dependency', 'BCNF condition.', 'Data Modeling & DBMS Fundamentals'),
('Determinant means?', '["Left side of FD","Right side of FD","Any attribute","Foreign key"]', 'Left side of FD', 'FD', 'Functional Dependency', 'Determinant LHS.', 'Data Modeling & DBMS Fundamentals'),
('Inference rules derive?', '["Implied FDs","ER models","Queries","Indexes"]', 'Implied FDs', 'FD', 'Functional Dependency', 'FD inference.', 'Data Modeling & DBMS Fundamentals');

-- 1NF (Atomic Values)
INSERT INTO quiz (question, options_text, correct_answer, nf_level, concept_tag, explanation, two_category) VALUES
('1NF requires?', '["Atomic values","No transitive dependencies","Every determinant is a key","No partial dependencies"]', 'Atomic values', '1NF', 'Atomic Values', '1NF uses atomic/indivisible values.', 'Normalization & Dependencies'),
('Which violates 1NF?', '["Multiple emails in one field","Foreign keys","Surrogate keys","Index"]', 'Multiple emails in one field', '1NF', 'Atomic Values', 'Repeating groups violate 1NF.', 'Normalization & Dependencies'),
('A repeating group suggests?', '["Not in 1NF","In 3NF","BCNF","All good"]', 'Not in 1NF', '1NF', 'Atomic Values', 'Repeating groups are non-atomic.', 'Normalization & Dependencies'),
('To achieve 1NF you should?', '["Split multivalued columns","Add foreign key","Add index","Use NULLs"]', 'Split multivalued columns', '1NF', 'Atomic Values', 'Decompose to atomic columns.', 'Normalization & Dependencies'),
('PhoneNumbers column storing CSV:', '["Violates 1NF","Satisfies 2NF","Is BCNF","OK if short"]', 'Violates 1NF', '1NF', 'Atomic Values', 'CSV is non-atomic.', 'Normalization & Dependencies'),
('Array type in a cell:', '["Likely violates 1NF","Enforces FD","Ensures 2NF","Ensures 3NF"]', 'Likely violates 1NF', '1NF', 'Atomic Values', 'Arrays usually non-atomic in RDBMS.', 'Normalization & Dependencies'),
('Pivoting rows to columns helps?', '["Enforce 1NF","Breaks 1NF","Unrelated","Ensures BCNF"]', 'Enforce 1NF', '1NF', 'Atomic Values', 'Normalization to atomic values.', 'Normalization & Dependencies'),
('Nested JSON in a field:', '["Violates 1NF typically","Enforces referential integrity","Ensures 3NF","Improves FDs"]', 'Violates 1NF typically', '1NF', 'Atomic Values', 'Nested structures are not atomic.', 'Normalization & Dependencies'),
('1NF focuses on?', '["Attribute atomicity","Key minimality","Determinants","Transitivity"]', 'Attribute atomicity', '1NF', 'Atomic Values', 'Focus on atomic values.', 'Normalization & Dependencies'),
('Which design is 1NF compliant?', '["One value per field","Composite values","CSV lists","Arrays"]', 'One value per field', '1NF', 'Atomic Values', 'Atomic values.', 'Normalization & Dependencies'),
('Split addresses into?', '["Street, City, Zip","Everything in one","CityZip","Random"]', 'Street, City, Zip', '1NF', 'Atomic Values', 'Atomic components.', 'Normalization & Dependencies'),
('Why 1NF first?', '["Foundation for higher NFs","To reach 4NF","For denormalization","For indexing"]', 'Foundation for higher NFs', '1NF', 'Atomic Values', 'Baseline normalization.', 'Normalization & Dependencies');

-- 2NF (Partial Dependency)
INSERT INTO quiz (question, options_text, correct_answer, nf_level, concept_tag, explanation, two_category) VALUES
('2NF removes?', '["Partial dependencies","Transitive dependencies","All anomalies","All redundancy"]', 'Partial dependencies', '2NF', 'Partial Dependency', '2NF eliminates dependency on part of a key.', 'Normalization & Dependencies'),
('Which indicates partial dependency?', '["Non-key depends on part of composite key","Every determinant is a key","Atomic values","A->B and B->C"]', 'Non-key depends on part of composite key', '2NF', 'Partial Dependency', 'Dependency on subset of key.', 'Normalization & Dependencies'),
('Table with key (CourseID, StudentID) and attribute CourseName:', '["Violates 2NF","Satisfies 3NF","BCNF","OK always"]', 'Violates 2NF', '2NF', 'Partial Dependency', 'CourseName depends only on CourseID.', 'Normalization & Dependencies'),
('To fix 2NF issue, you should?', '["Decompose into separate tables","Add index","Add surrogate key","Denormalize"]', 'Decompose into separate tables', '2NF', 'Partial Dependency', 'Split attributes depending only on part of key.', 'Normalization & Dependencies'),
('2NF requires first?', '["1NF","3NF","BCNF","5NF"]', '1NF', '2NF', 'Partial Dependency', 'Hierarchy of NFs.', 'Normalization & Dependencies'),
('Which table is in 2NF?', '["Non-keys depend on full key","Non-keys depend on part key","Transitive deps exist","Repeating groups present"]', 'Non-keys depend on full key', '2NF', 'Partial Dependency', 'No partial deps.', 'Normalization & Dependencies'),
('Composite key dependencies imply?', '["Check for partial deps","All good","Transitive deps only","1NF satisfied"]', 'Check for partial deps', '2NF', 'Partial Dependency', 'Be wary of subsets.', 'Normalization & Dependencies'),
('A lookup table for CourseName:', '["Removes partial dep","Adds transitive dep","Unrelated","Breaks 1NF"]', 'Removes partial dep', '2NF', 'Partial Dependency', 'Separate Course to its own table.', 'Normalization & Dependencies'),
('Which statement is true?', '["2NF forbids dependency on subset of key","2NF equals 3NF","2NF forbids nulls","2NF requires arrays"]', '2NF forbids dependency on subset of key', '2NF', 'Partial Dependency', 'Definition.', 'Normalization & Dependencies'),
('2NF primarily addresses?', '["Composite key situations","Single key columns","ER modeling","Indexing"]', 'Composite key situations', '2NF', 'Partial Dependency', 'Partial deps appear with composite keys.', 'Normalization & Dependencies'),
('Non-key attribute depends on?', '["Entire primary key","Any non-key","Single foreign key","Arbitrary subset"]', 'Entire primary key', '2NF', 'Partial Dependency', 'Requirement for 2NF.', 'Normalization & Dependencies'),
('Which is a sign of not 2NF?', '["Redundancy tied to part of key","Every determinant is key","Atomic values only","BCNF present"]', 'Redundancy tied to part of key', '2NF', 'Partial Dependency', 'Partial dependency redundancy.', 'Normalization & Dependencies');

-- 3NF (Transitive Dependency)
INSERT INTO quiz (question, options_text, correct_answer, nf_level, concept_tag, explanation, two_category) VALUES
('3NF removes?', '["Transitive dependencies","Partial dependencies","Repeating groups","All keys"]', 'Transitive dependencies', '3NF', 'Transitive Dependency', '3NF eliminates non-key -> non-key dependencies.', 'Normalization & Dependencies'),
('Which implies transitive dependency?', '["A->B, B->C, A not key","Key->NonKey","Atomic values","Part key dependency"]', 'A->B, B->C, A not key', '3NF', 'Transitive Dependency', 'A determines C via B.', 'Normalization & Dependencies'),
('Employee(EmpID, DeptID, DeptName) violates?', '["3NF","1NF","2NF","None"]', '3NF', '3NF', 'Transitive Dependency', 'DeptName depends on DeptID not EmpID directly.', 'Normalization & Dependencies'),
('To fix 3NF issue, you should?', '["Separate Dept into new table","Add composite key","Add array column","Use denormalization"]', 'Separate Dept into new table', '3NF', 'Transitive Dependency', 'Remove transitive dependency.', 'Normalization & Dependencies'),
('3NF requires first?', '["2NF","BCNF","1NF","5NF"]', '2NF', '3NF', 'Transitive Dependency', 'Order of normalization.', 'Normalization & Dependencies'),
('3NF condition mentions?', '["Non-key depends only on keys","Only atomic values","Every determinant a key","No foreign keys"]', 'Non-key depends only on keys', '3NF', 'Transitive Dependency', 'No non-key -> non-key.', 'Normalization & Dependencies'),
('If A->B and B not key and B->C:', '["A->C breaks 3NF","OK","1NF issue","2NF only"]', 'A->C breaks 3NF', '3NF', 'Transitive Dependency', 'Transitive dependency.', 'Normalization & Dependencies'),
('Surrogate keys guarantee 3NF?', '["No","Yes always","Only with arrays","Only in BCNF"]', 'No', '3NF', 'Transitive Dependency', '3NF is about dependencies, not surrogate keys.', 'Normalization & Dependencies'),
('3NF helps reduce?', '["Update anomalies","Query speed","Index size","Joins"]', 'Update anomalies', '3NF', 'Transitive Dependency', 'Normalization reduces anomalies.', 'Normalization & Dependencies'),
('Which is allowed in 3NF?', '["Key -> NonKey","NonKey -> NonKey","PartKey -> NonKey","Repeating groups"]', 'Key -> NonKey', '3NF', 'Transitive Dependency', 'Key determines NonKey is fine.', 'Normalization & Dependencies'),
('Attribute that determines non-key is?', '["Transitive determinant","Foreign key","Prime attribute","Null"]', 'Transitive determinant', '3NF', 'Transitive Dependency', 'Terminology.', 'Normalization & Dependencies'),
('3NF vs BCNF difference?', '["BCNF stricter on determinants","3NF stricter","They are identical","BCNF about arrays"]', 'BCNF stricter on determinants', '3NF', 'Transitive Dependency', 'BCNF is stronger than 3NF.', 'Normalization & Dependencies');

-- Baseline attempts/responses for demo student
INSERT OR IGNORE INTO attempt (attempt_id, student_id, nf_scope, started_at, finished_at, items_total, items_correct, score_pct, source) VALUES
(1, 1, 'FD+1NF', datetime('now', '-5 day'), datetime('now', '-5 day', '+15 minutes'), 12, 10, 83.3, 'live'),
(2, 1, '2NF+3NF', datetime('now', '-2 day'), datetime('now', '-2 day', '+18 minutes'), 12, 8, 66.7, 'live');

INSERT OR IGNORE INTO response (attempt_id, student_id, quiz_id, answer, score, response_time_s)
SELECT 1, 1, q.quiz_id, q.correct_answer, 1, 12.0
FROM quiz q
WHERE q.nf_level IN ('FD', '1NF')
  AND q.quiz_id IN (
    SELECT quiz_id FROM quiz WHERE nf_level IN ('FD', '1NF') ORDER BY quiz_id LIMIT 12
  );

INSERT OR IGNORE INTO response (attempt_id, student_id, quiz_id, answer, score, response_time_s)
SELECT 2, 1, q.quiz_id, q.correct_answer, CASE WHEN q.rn <= 3 THEN 1 ELSE 0 END, 14.0
FROM (
    SELECT quiz_id, correct_answer, nf_level,
           ROW_NUMBER() OVER (PARTITION BY nf_level ORDER BY quiz_id) AS rn
    FROM quiz
    WHERE nf_level IN ('2NF', '3NF')
) AS q
WHERE q.rn <= 6;
