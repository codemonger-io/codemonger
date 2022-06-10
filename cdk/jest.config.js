module.exports = {
  testEnvironment: 'node',
  roots: ['<rootDir>/test'],
  testMatch: ['**/*.test.ts'],
  transform: {
    '^.+\\.tsx?$': 'ts-jest',
    // processes JS files in the cloudfront-fn with Babel + babel-plugin-rewire
    // so that internal handlers can be tested.
    '^.+cloudfront-fn.+\\.js$': 'babel-jest',
  }
};
