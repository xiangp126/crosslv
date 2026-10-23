"""HTML escaping and link bases."""
import html

GERRIT = 'https://git-nbu.nvidia.com/r/c/golan_fw/+/'
GERRIT_UTOPX = 'https://git-nbu.nvidia.com/r/c/fw_ver/utopx/+/'
GERRIT_UDRIVER = 'https://git-nbu.nvidia.com/r/c/hca_fw/udriver/+/'
GERRIT_AUTOMATION = 'https://git-nbu.nvidia.com/r/c/hca_fw/fw_automations/+/'
REDMINE = 'https://redmine.nvidia.com/issues/'


def esc(s):
    return html.escape(s, quote=True)
