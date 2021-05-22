from setuptools import find_packages, setup

setup(
      name='newvelles',
      version='0.0.3',
      description='Command line tool fetch news with a Twist.',
      url='https://github.com/glhuilli/newvelles',
      author="Gaston L'Huillier",
      author_email='glhuilli@gmail.com',
      license='MIT License',
      packages=find_packages(),
      package_data={
            '': ['LICENSE', '*.ini']
      },
      zip_safe=False,
      install_requires=[x.strip() for x in open("requirements.txt").readlines()],
      entry_points={
        'console_scripts': ['newvelles=newvelles.__main__:main'],
      }
)
