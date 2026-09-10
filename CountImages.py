from pathlib import Path

# Supported image formats
IMAGE_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".gif",
    ".bmp",
    ".tiff",
    ".svg",
}


def count_images_in_folders(folder_paths, include_subfolders=True):
  """Counts images in a list of given folder paths.

  :param folder_paths: List of directory path strings
  :param include_subfolders: If True, counts images inside subfolders as well
  """
  results = {}

  for folder in folder_paths:
    path = Path(folder)

    if not path.exists():
      results[folder] = "Error: Folder not found"
      continue

    if not path.is_dir():
      results[folder] = "Error: Path is not a directory"
      continue

    # Search pattern based on recursive option
    files = path.rglob("*") if include_subfolders else path.glob("*")

    # Filter files by image extension
    image_count = sum(
        1
        for file in files
        if file.is_file() and file.suffix.lower() in IMAGE_EXTENSIONS
    )

    results[folder] = image_count

  return results


# ==========================================
# EXAMPLE USAGE
# ==========================================
if __name__ == "__main__":
  # Add your folder paths here (works with absolute or relative paths)
  folders_to_check = [
      r"E:\PycharmProjects\pythonProject\weekly_5yr_charts\is_new_yes",
      r"E:\PycharmProjects\pythonProject\weekly_5yr_indian_charts\is_new_yes",
      r"./weekly_5yr_charts_by_category_usa",
      r"./weekly_5yr_charts_by_category",
  ]

  # Set include_subfolders=False if you only want top-level image counts
  counts = count_images_in_folders(folders_to_check, include_subfolders=True)

  print("\n--- Image Count Results ---")
  for folder, count in counts.items():
    print(f"📁 {folder}: {count}")