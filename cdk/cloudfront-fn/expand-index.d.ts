// this declaration exists only for unit tests.

type Event = {
  request: Request;
};
type Request = {
  uri: string;
}

function splitStringByFirst(str: string, delimiter: string): string[];
function splitStringByLast(str: string, delimiter: string): string[];
function handlerImpl(event: Event): Request;

// declaration of the __get__ function injected by babel-plugin-rewire.
export function __get__(name: 'splitStringByFirst'): splitStringByFirst;
export function __get__(name: 'splitStringByLast'): splitStringByLast;
export function __get__(name: 'handlerImpl'): handlerImpl;
