import os


def chmod(path, mode):
    """
    Change access mode on a target directory entry. Do not follow symlinks if the platform supports it.

    :param path: path to the file
    :param mode: mode to be set
    :return:
    """
    if os.chmod in os.supports_follow_symlinks:
        os.chmod(path, mode, follow_symlinks=False)
    else:
        pass
