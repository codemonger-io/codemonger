// thanks to babel-plugin-rewire all *.js modules expose internal functions
// through the __get__ function.
import { __get__ } from '../../cloudfront-fn/expand-index.js';
const splitStringByFirst = __get__('splitStringByFirst');
const splitStringByLast = __get__('splitStringByLast');
const handlerImpl = __get__('handlerImpl');

describe('expand-index', () => {
  describe('splitStringByFirst', () => {
    it('("/abc?d=ef", "?") should return ["/abc", "?d=ef"]', () => {
      expect(splitStringByFirst('/abc?d=ef', '?')).toEqual(['/abc', '?d=ef']);
    });

    it('("/abc#def#ghi#jkl", "#") should return ["/abc", "#def#ghi#jkl"]', () => {
      expect(splitStringByFirst('/abc#def#ghi#jkl', '#'))
        .toEqual(['/abc', '#def#ghi#jkl']);
    });

    it('("/abc?d=ef", "#") should return ["/abc?d=ef", ""]', () => {
      expect(splitStringByFirst('/abc?d=ef', '#')).toEqual(['/abc?d=ef', '']);
    });

    it('("/abc#", "#") should return ["/abc", "#"]', () => {
      expect(splitStringByFirst('/abc#', '#')).toEqual(['/abc', '#']);
    });

    it('("", "/") should return ["", ""]', () => {
      expect(splitStringByFirst('', '/')).toEqual(['', '']);
    });
  });

  describe('splitStringByLast', () => {
    it('("/abc?d=ef", "?") should return ["/abc", "?d=ef"]', () => {
      expect(splitStringByLast('/abc?d=ef', '?')).toEqual(['/abc', '?d=ef']);
    });

    it('("/abc/def/ghi/jkl", "/") should return ["/abc/def/ghi", "/jkl"]', () => {
      expect(splitStringByLast('/abc/def/ghi/jkl', '/'))
        .toEqual(['/abc/def/ghi', '/jkl']);
    });

    it('("/abc?d=ef", "#") should return ["/abc?d=ef", ""]', () => {
      expect(splitStringByLast('/abc?d=ef', '#')).toEqual(['/abc?d=ef', '']);
    });

    it('("/abc/", "/") should return ["/abc", "/"]', () => {
      expect(splitStringByLast('/abc/', '/')).toEqual(['/abc', '/']);
    });

    it('("", "/") should return ["", ""]', () => {
      expect(splitStringByLast('', '/')).toEqual(['', '']);
    });
  });

  describe('handlerImpl(event)', () => {
    it('should change event.request.uri "/" into "/index.html"', () => {
      expect(handlerImpl({
        request: {
          uri: '/',
        },
      })).toEqual({
        uri: '/index.html',
      });
    });

    it('should change event.request.uri "/blog" into "/blog/index.html"', () => {
      expect(handlerImpl({
        request: {
          uri: '/blog',
        },
      })).toEqual({
        uri: '/blog/index.html',
      });
    });

    it('should change event.request.uri "/blog/post001" into "/blog/post001/index.html"', () => {
      expect(handlerImpl({
        request: {
          uri: '/blog/post001',
        },
      })).toEqual({
        uri: '/blog/post001/index.html',
      });
    });

    it('should change event.request.uri "/blog/post001/" into "/blog/post001/index.html"', () => {
      expect(handlerImpl({
        request: {
          uri: '/blog/post001/',
        },
      })).toEqual({
        uri: '/blog/post001/index.html',
      });
    });

    it('should change event.request.uri "/blog/post001#section-a" into "/blog/post001/index.html#section-a"', () => {
      expect(handlerImpl({
        request: {
          uri: '/blog/post001#section-a',
        },
      })).toEqual({
        uri: '/blog/post001/index.html#section-a',
      });
    });

    it('should change event.request.uri "/blog/post001/?param=1&param=2#containing#and/" into "/blog/post001/index.html?param=1&param=2#containing#and/"', () => {
      expect(handlerImpl({
        request: {
          uri: '/blog/post001/?param=1&param=2#containing#and/',
        },
      })).toEqual({
        uri: '/blog/post001/index.html?param=1&param=2#containing#and/',
      });
    });

    it('should not change event.request.uri "/codemonger.svg"', () => {
      expect(handlerImpl({
        request: {
          uri: '/codemonger.svg',
        },
      })).toEqual({
        uri: '/codemonger.svg',
      });
    });

    it('should change event.request.uri "/codemonger.svg/" into "/codemonger.svg/index.html"', () => {
      expect(handlerImpl({
        request: {
          uri: '/codemonger.svg/',
        },
      })).toEqual({
        uri: '/codemonger.svg/index.html',
      });
    });
  });
});
