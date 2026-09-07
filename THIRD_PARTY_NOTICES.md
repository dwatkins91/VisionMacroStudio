# Third-party notices

Vision Macro Studio is licensed under the GNU Affero General Public License
version 3 or later. It depends on separately maintained open-source projects.
Those projects retain their own copyright and license terms.

The list below describes the direct runtime and build dependencies declared by
this repository. A portable build may also contain their transitive
dependencies. Consult the installed package metadata and upstream project for
the exact terms applying to a particular binary build.

| Component | Purpose | Upstream license | Project |
| --- | --- | --- | --- |
| Ultralytics | YOLO training and inference | AGPL-3.0 by default | <https://github.com/ultralytics/ultralytics> |
| PyTorch | Machine-learning runtime | BSD-3-Clause | <https://github.com/pytorch/pytorch> |
| TorchVision | Vision operations and models | BSD-3-Clause | <https://github.com/pytorch/vision> |
| PySide6 / Qt for Python | Desktop interface | LGPL-3.0-only, GPL, or commercial terms depending on the component | <https://doc.qt.io/qtforpython-6/licenses.html> |
| OpenCV Python | Image processing and previews | Apache-2.0 | <https://github.com/opencv/opencv-python> |
| NumPy | Array processing | BSD-3-Clause | <https://github.com/numpy/numpy> |
| Pillow | Image loading and saving | HPND | <https://github.com/python-pillow/Pillow> |
| MSS | Screen capture | MIT | <https://github.com/BoboTiG/python-mss> |
| pynput | Keyboard, mouse, and global hotkeys | LGPL-3.0 | <https://github.com/moses-palmer/pynput> |
| PyYAML | Dataset configuration | MIT | <https://github.com/yaml/pyyaml> |
| PyInstaller | Windows packaging tool | GPL-2.0-or-later with a bootloader exception | <https://github.com/pyinstaller/pyinstaller> |

The Windows portable builder copies license files exposed by installed Python
package metadata into `THIRD_PARTY_LICENSES` when they are available. Absence
of a copied text does not remove or replace the dependency's license.

Ultralytics states that its code and trained models are AGPL-3.0 by default.
Anyone who cannot meet those open-source conditions should review Ultralytics'
current licensing options before distributing a modified or proprietary build:
<https://www.ultralytics.com/license>.
