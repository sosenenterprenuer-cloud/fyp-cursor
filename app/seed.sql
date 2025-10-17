PRAGMA foreign_keys=ON;

-- Modules per concept tag
INSERT INTO module (title, description, nf_level, concept_tag, resource_url) VALUES
('Functional Dependencies 101', 'Understand determinants and implied attributes', 'FD', 'Functional Dependency', 'https://en.wikipedia.org/wiki/Functional_dependency'),
('First Normal Form (1NF)', 'Atomic values, no repeating groups', '1NF', 'Atomic Values', 'https://en.wikipedia.org/wiki/First_normal_form'),
('Second Normal Form (2NF)', 'Eliminate partial dependencies', '2NF', 'Partial Dependency', 'https://en.wikipedia.org/wiki/Second_normal_form'),
('Third Normal Form (3NF)', 'Eliminate transitive dependencies', '3NF', 'Transitive Dependency', 'https://en.wikipedia.org/wiki/Third_normal_form');

INSERT OR IGNORE INTO lecturer (name, email, password_hash)
VALUES (
  'Admin Lecturer',
  'admin@lct.edu',
  'scrypt:32768:8:1$wTlANxNNLLoNn4Uq$6ccbf5f9217be922980d987781fad29737537e9918d31791911222b0b29e968a8b33d3a76ec72a35947ad940a72167c64d76c7e1645ca2b9d6a41fe2ea2cc7d8'
);

-- Helper for generating sample questions; options_text: JSON array of 4 strings
-- At least 12 per NF level: FD, 1NF, 2NF, 3NF

-- FD (Functional Dependency)
INSERT INTO quiz (question, options_text, correct_answer, nf_level, concept_tag, explanation) VALUES
('In relation Orders(OrderID, CustomerID, OrderDate), which FD holds?', '["OrderID -> CustomerID, OrderDate","CustomerID -> OrderID","OrderDate -> OrderID","CustomerID, OrderDate -> OrderID"]', 'OrderID -> CustomerID, OrderDate', 'FD', 'Functional Dependency', 'Primary key determines other attributes.'),
('Which best defines a functional dependency?', '["One attribute uniquely determines another","All attributes are atomic","No partial key dependencies","No transitive dependencies"]', 'One attribute uniquely determines another', 'FD', 'Functional Dependency', 'FD defines unique determination.'),
('Given A -> B and B -> C, which holds?', '["A -> C","C -> A","A -> B is transitive","No dependency"]', 'A -> C', 'FD', 'Functional Dependency', 'Transitivity of FDs.'),
('What is a candidate key?', '["Minimal set determining all attributes","Any non-key attribute","Foreign key","Superkey with redundancy"]', 'Minimal set determining all attributes', 'FD', 'Functional Dependency', 'Candidate key minimality.'),
('If AB is a key, which is true?', '["AB -> all attributes","A -> all attributes","B -> all attributes","None"]', 'AB -> all attributes', 'FD', 'Functional Dependency', 'Key determines all attributes.'),
('Which violates FD theory?', '["Two rows share key but differ in non-key","Surrogate key used","Nulls in nullable columns","Composite keys used"]', 'Two rows share key but differ in non-key', 'FD', 'Functional Dependency', 'FD violation when non-key differs for same key.'),
('Armstrong axioms include?', '["Reflexivity, Augmentation, Transitivity","Commutativity, Distributivity","Normalization, Denormalization","BCNF, 4NF"]', 'Reflexivity, Augmentation, Transitivity', 'FD', 'Functional Dependency', 'Classical axioms.'),
('Closure of attribute set is?', '["All attributes determined by it","Only keys","Only FDs","All non-keys"]', 'All attributes determined by it', 'FD', 'Functional Dependency', 'Attribute closure.'),
('Which is always true?', '["Key -> every attribute","Non-key -> key","Date -> ID","City -> Country always"]', 'Key -> every attribute', 'FD', 'Functional Dependency', 'Definition of key.'),
('BCNF requires?', '["Every determinant is a key","No nulls","Single-attribute keys only","No foreign keys"]', 'Every determinant is a key', 'FD', 'Functional Dependency', 'BCNF condition.'),
('Determinant means?', '["Left side of FD","Right side of FD","Any attribute","Foreign key"]', 'Left side of FD', 'FD', 'Functional Dependency', 'Determinant LHS.'),
('Inference rules derive?', '["Implied FDs","ER models","Queries","Indexes"]', 'Implied FDs', 'FD', 'Functional Dependency', 'FD inference.');

-- 1NF (Atomic Values)
INSERT INTO quiz (question, options_text, correct_answer, nf_level, concept_tag, explanation) VALUES
('1NF requires?', '["Atomic values","No transitive dependencies","Every determinant is a key","No partial dependencies"]', 'Atomic values', '1NF', 'Atomic Values', '1NF uses atomic/indivisible values.'),
('Which violates 1NF?', '["Multiple emails in one field","Foreign keys","Surrogate keys","Index"]', 'Multiple emails in one field', '1NF', 'Atomic Values', 'Repeating groups violate 1NF.'),
('A repeating group suggests?', '["Not in 1NF","In 3NF","BCNF","All good"]', 'Not in 1NF', '1NF', 'Atomic Values', 'Repeating groups are non-atomic.'),
('To achieve 1NF you should?', '["Split multivalued columns","Add foreign key","Add index","Use NULLs"]', 'Split multivalued columns', '1NF', 'Atomic Values', 'Decompose to atomic columns.'),
('PhoneNumbers column storing CSV:', '["Violates 1NF","Satisfies 2NF","Is BCNF","OK if short"]', 'Violates 1NF', '1NF', 'Atomic Values', 'CSV is non-atomic.'),
('Array type in a cell:', '["Likely violates 1NF","Enforces FD","Ensures 2NF","Ensures 3NF"]', 'Likely violates 1NF', '1NF', 'Atomic Values', 'Arrays usually non-atomic in RDBMS.'),
('Pivoting rows to columns helps?', '["Enforce 1NF","Breaks 1NF","Unrelated","Ensures BCNF"]', 'Enforce 1NF', '1NF', 'Atomic Values', 'Normalization to atomic values.'),
('Nested JSON in a field:', '["Violates 1NF typically","Enforces referential integrity","Ensures 3NF","Improves FDs"]', 'Violates 1NF typically', '1NF', 'Atomic Values', 'Nested structures are not atomic.'),
('1NF focuses on?', '["Attribute atomicity","Key minimality","Determinants","Transitivity"]', 'Attribute atomicity', '1NF', 'Atomic Values', 'Focus on atomic values.'),
('Which design is 1NF compliant?', '["One value per field","Composite values","CSV lists","Arrays"]', 'One value per field', '1NF', 'Atomic Values', 'Atomic values.'),
('Split addresses into?', '["Street, City, Zip","Everything in one","CityZip","Random"]', 'Street, City, Zip', '1NF', 'Atomic Values', 'Atomic components.'),
('Why 1NF first?', '["Foundation for higher NFs","To reach 4NF","For denormalization","For indexing"]', 'Foundation for higher NFs', '1NF', 'Atomic Values', 'Baseline normalization.');

-- 2NF (Partial Dependency)
INSERT INTO quiz (question, options_text, correct_answer, nf_level, concept_tag, explanation) VALUES
('2NF removes?', '["Partial dependencies","Transitive dependencies","All anomalies","All redundancy"]', 'Partial dependencies', '2NF', 'Partial Dependency', '2NF eliminates dependency on part of a key.'),
('Which indicates partial dependency?', '["Non-key depends on part of composite key","Every determinant is a key","Atomic values","A->B and B->C"]', 'Non-key depends on part of composite key', '2NF', 'Partial Dependency', 'Dependency on subset of key.'),
('Table with key (CourseID, StudentID) and attribute CourseName:', '["Violates 2NF","Satisfies 3NF","BCNF","OK always"]', 'Violates 2NF', '2NF', 'Partial Dependency', 'CourseName depends only on CourseID.'),
('To fix 2NF issue, you should?', '["Decompose into separate tables","Add index","Add surrogate key","Denormalize"]', 'Decompose into separate tables', '2NF', 'Partial Dependency', 'Split attributes depending only on part of key.'),
('2NF requires first?', '["1NF","3NF","BCNF","5NF"]', '1NF', '2NF', 'Partial Dependency', 'Hierarchy of NFs.'),
('Which table is in 2NF?', '["Non-keys depend on full key","Non-keys depend on part key","Transitive deps exist","Repeating groups present"]', 'Non-keys depend on full key', '2NF', 'Partial Dependency', 'No partial deps.'),
('Composite key dependencies imply?', '["Check for partial deps","All good","Transitive deps only","1NF satisfied"]', 'Check for partial deps', '2NF', 'Partial Dependency', 'Be wary of subsets.'),
('A lookup table for CourseName:', '["Removes partial dep","Adds transitive dep","Unrelated","Breaks 1NF"]', 'Removes partial dep', '2NF', 'Partial Dependency', 'Separate Course to its own table.'),
('Which statement is true?', '["2NF forbids dependency on subset of key","2NF equals 3NF","2NF forbids nulls","2NF requires arrays"]', '2NF forbids dependency on subset of key', '2NF', 'Partial Dependency', 'Definition.'),
('2NF primarily addresses?', '["Composite key situations","Single key columns","ER modeling","Indexing"]', 'Composite key situations', '2NF', 'Partial Dependency', 'Partial deps appear with composite keys.'),
('Non-key attribute depends on?', '["Entire primary key","Any non-key","Single foreign key","Arbitrary subset"]', 'Entire primary key', '2NF', 'Partial Dependency', 'Requirement for 2NF.'),
('Which is a sign of not 2NF?', '["Redundancy tied to part of key","Every determinant is key","Atomic values only","BCNF present"]', 'Redundancy tied to part of key', '2NF', 'Partial Dependency', 'Partial dependency redundancy.');

-- 3NF (Transitive Dependency)
INSERT INTO quiz (question, options_text, correct_answer, nf_level, concept_tag, explanation) VALUES
('3NF removes?', '["Transitive dependencies","Partial dependencies","Repeating groups","All keys"]', 'Transitive dependencies', '3NF', 'Transitive Dependency', '3NF eliminates non-key -> non-key dependencies.'),
('Which implies transitive dependency?', '["A->B, B->C, A not key","Key->NonKey","Atomic values","Part key dependency"]', 'A->B, B->C, A not key', '3NF', 'Transitive Dependency', 'A determines C via B.'),
('Employee(EmpID, DeptID, DeptName) violates?', '["3NF","1NF","2NF","None"]', '3NF', '3NF', 'Transitive Dependency', 'DeptName depends on DeptID not EmpID directly.'),
('To fix 3NF issue, you should?', '["Separate Dept into new table","Add composite key","Add array column","Use denormalization"]', 'Separate Dept into new table', '3NF', 'Transitive Dependency', 'Remove transitive dependency.'),
('3NF requires first?', '["2NF","BCNF","1NF","5NF"]', '2NF', '3NF', 'Transitive Dependency', 'Order of normalization.'),
('3NF condition mentions?', '["Non-key depends only on keys","Only atomic values","Every determinant a key","No foreign keys"]', 'Non-key depends only on keys', '3NF', 'Transitive Dependency', 'No non-key -> non-key.'),
('If A->B and B not key and B->C:', '["A->C breaks 3NF","OK","1NF issue","2NF only"]', 'A->C breaks 3NF', '3NF', 'Transitive Dependency', 'Transitive dependency.'),
('Surrogate keys guarantee 3NF?', '["No","Yes always","Only with arrays","Only in BCNF"]', 'No', '3NF', 'Transitive Dependency', '3NF is about dependencies, not surrogate keys.'),
('3NF helps reduce?', '["Update anomalies","Query speed","Index size","Joins"]', 'Update anomalies', '3NF', 'Transitive Dependency', 'Normalization reduces anomalies.'),
('Which is allowed in 3NF?', '["Key -> NonKey","NonKey -> NonKey","PartKey -> NonKey","Repeating groups"]', 'Key -> NonKey', '3NF', 'Transitive Dependency', 'Key determines NonKey is fine.'),
('Attribute that determines non-key is?', '["Transitive determinant","Foreign key","Prime attribute","Null"]', 'Transitive determinant', '3NF', 'Transitive Dependency', 'Terminology.'),
('3NF vs BCNF difference?', '["BCNF stricter on determinants","3NF stricter","They are identical","BCNF about arrays"]', 'BCNF stricter on determinants', '3NF', 'Transitive Dependency', 'BCNF is stronger than 3NF.');
