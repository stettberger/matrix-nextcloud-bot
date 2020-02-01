from setuptools import setup

setup(
   name='matrix-nextcloud-bot',
   version='0.1',
   description='Moving Files and Pictures from a Matrix Channel to the nextcloud',
   author='Christian Dietrich',
   author_email='stettberger@dokucode.de',
   packages=['mnb'],  #same as name
   install_requires=['nio', 'xdg',
                     'nextcloud @ git+https://github.com/EnterpriseyIntranet/nextcloud-API.git'], #external packages as dependencies
   scripts=["bin/matrix-nextcloud-bot"]
)
