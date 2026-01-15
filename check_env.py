import sys
import importlib.util
import importlib.metadata

def check_package(package_name):
    try:
        dist = importlib.metadata.distribution(package_name)
        print(f"✅ {package_name} is installed: {dist.version}")
        return True
    except importlib.metadata.PackageNotFoundError:
        print(f"❌ {package_name} is NOT installed")
        return False
    except Exception as e:
        print(f"⚠️ Error checking {package_name}: {e}")
        return False

def check_import(module_name):
    try:
        importlib.import_module(module_name)
        print(f"✅ Import '{module_name}' successful")
        return True
    except ImportError as e:
        print(f"❌ Import '{module_name}' failed: {e}")
        return False
    except Exception as e:
        print(f"⚠️ Error importing {module_name}: {e}")
        return False

print("--- Environment Check ---")
print(f"Python: {sys.version}")

pkg_ok = check_package("google-genai")
legacy_pkg = check_package("google-generativeai")

if legacy_pkg:
    print("⚠️  Legacy package 'google-generativeai' is installed. It might conflict if namespace is broken.")

import_ok = check_import("google.genai")

if pkg_ok and import_ok:
    print("\n🎉 Environment looks good!")
else:
    print("\n🚨 Environment has issues. Try running update.sh again.")
