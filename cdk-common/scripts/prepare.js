// This script will circumvent the situtation where no dependencies have been
// installed before running the `prepare` life cycle script.
//
// ## Background
//
// This subproject is inteded to be linked from other subprojects in the same
// repository using `npm link --save ../cdk-common`.
// This project transpiles TypeScript code, i.e., `npm run build`, during the
// `prepare` life cycle script.
// Unfortunately, `npm link` does not install dependencies of this project
// before running the `prepare` script.
// And the `prepare` script ends up with a "no such package" error.
//
// This error can be avoided by running `npm install` in this project before
// resolving dependencies of other subprojects depending on this project.
// However, this is not very intuitive that I want an automated solution.
//
// ## Workaround
//
// This script invokes `npm install` before running `npm run build` to make sure
// that dependencies are installed.
// But simply invoking `npm install` from the `prepare` script makes an infinite
// loop of `prepare` → `install` → `prepare` → ...
// So this script skips invoking `npm install` if a `node_module` folder already
// exists in this project.

const childProcess = require('child_process');
const fs = require('fs');
const process = require('process');
const util = require('util');

const promiseExec = util.promisify(childProcess.exec);

const NPM_INSTALL = 'npm install';
const NPM_BUILD = 'npm run build';

console.log('preparing...', process.cwd());

fs.stat('./node_modules', (err, stats) => {
  if (err != null && err.code !== 'ENOENT') {
    console.error('failed to stat', err);
    process.exit(1);
  }
  let installation;
  if (stats != null && stats.isDirectory()) {
    // skips intallation because there is `node_modules` folder.
    installation = Promise.resolve();
  } else {
    installation = promiseExec(NPM_INSTALL);
  }
  installation
    .then(() => {
      promiseExec(NPM_BUILD)
        .then(() => {
          process.exit(0);
        })
        .catch(err => {
          console.error('failed to build', err);
          process.exit(1);
        });
    })
    .catch(err => {
      console.error('failed to install', err);
      process.exit(1);
    });
});
