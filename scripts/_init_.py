 (cd "$(git rev-parse --show-toplevel)" && git apply --3way <<'EOF' 
diff --git a/scripts/__init__.py b/scripts/__init__.py
new file mode 100644
index 0000000000000000000000000000000000000000..f79c736dea23a0832ee43e24c29759f75227532f
--- /dev/null
+++ b/scripts/__init__.py
@@ -0,0 +1 @@
+"""Helper package for maintenance scripts."""
 
EOF
)