const electron = require('@webdriverio/electron-service');

module.exports = {
  capabilities: [{
    platformName: 'any',
    'wdio:electronService': {
      appBinaryPath: 'Example.app',
    },
  }],
  services: [electron],
};
