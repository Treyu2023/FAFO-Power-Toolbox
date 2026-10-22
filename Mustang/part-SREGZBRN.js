import {
  __commonJS,
  __toESM
} from "./part-MA4KR6TC.js";

// node_modules/react/cjs/react.development.js
var require_react_development = __commonJS({
  "node_modules/react/cjs/react.development.js"(exports, module) {
    "use strict";
    (function() {
      function defineDeprecationWarning(methodName, info) {
        Object.defineProperty(Component.prototype, methodName, {
          get: function() {
            console.warn(
              "%s(...) is deprecated in plain JavaScript React classes. %s",
              info[0],
              info[1]
            );
          }
        });
      }
      function getIteratorFn(maybeIterable) {
        if (null === maybeIterable || "object" !== typeof maybeIterable)
          return null;
        maybeIterable = MAYBE_ITERATOR_SYMBOL && maybeIterable[MAYBE_ITERATOR_SYMBOL] || maybeIterable["@@iterator"];
        return "function" === typeof maybeIterable ? maybeIterable : null;
      }
      function warnNoop(publicInstance, callerName) {
        publicInstance = (publicInstance = publicInstance.constructor) && (publicInstance.displayName || publicInstance.name) || "ReactClass";
        var warningKey = publicInstance + "." + callerName;
        didWarnStateUpdateForUnmountedComponent[warningKey] || (console.error(
          "Can't call %s on a component that is not yet mounted. This is a no-op, but it might indicate a bug in your application. Instead, assign to `this.state` directly or define a `state = {};` class property with the desired state in the %s component.",
          callerName,
          publicInstance
        ), didWarnStateUpdateForUnmountedComponent[warningKey] = true);
      }
      function Component(props, context, updater) {
        this.props = props;
        this.context = context;
        this.refs = emptyObject;
        this.updater = updater || ReactNoopUpdateQueue;
      }
      function ComponentDummy() {
      }
      function PureComponent(props, context, updater) {
        this.props = props;
        this.context = context;
        this.refs = emptyObject;
        this.updater = updater || ReactNoopUpdateQueue;
      }
      function noop() {
      }
      function testStringCoercion(value) {
        return "" + value;
      }
      function checkKeyStringCoercion(value) {
        try {
          testStringCoercion(value);
          var JSCompiler_inline_result = false;
        } catch (e) {
          JSCompiler_inline_result = true;
        }
        if (JSCompiler_inline_result) {
          JSCompiler_inline_result = console;
          var JSCompiler_temp_const = JSCompiler_inline_result.error;
          var JSCompiler_inline_result$jscomp$0 = "function" === typeof Symbol && Symbol.toStringTag && value[Symbol.toStringTag] || value.constructor.name || "Object";
          JSCompiler_temp_const.call(
            JSCompiler_inline_result,
            "The provided key is an unsupported type %s. This value must be coerced to a string before using it here.",
            JSCompiler_inline_result$jscomp$0
          );
          return testStringCoercion(value);
        }
      }
      function getComponentNameFromType(type) {
        if (null == type) return null;
        if ("function" === typeof type)
          return type.$$typeof === REACT_CLIENT_REFERENCE ? null : type.displayName || type.name || null;
        if ("string" === typeof type) return type;
        switch (type) {
          case REACT_FRAGMENT_TYPE:
            return "Fragment";
          case REACT_PROFILER_TYPE:
            return "Profiler";
          case REACT_STRICT_MODE_TYPE:
            return "StrictMode";
          case REACT_SUSPENSE_TYPE:
            return "Suspense";
          case REACT_SUSPENSE_LIST_TYPE:
            return "SuspenseList";
          case REACT_ACTIVITY_TYPE:
            return "Activity";
          case REACT_VIEW_TRANSITION_TYPE:
            return "ViewTransition";
        }
        if ("object" === typeof type)
          switch ("number" === typeof type.tag && console.error(
            "Received an unexpected object in getComponentNameFromType(). This is likely a bug in React. Please file an issue."
          ), type.$$typeof) {
            case REACT_PORTAL_TYPE:
              return "Portal";
            case REACT_CONTEXT_TYPE:
              return type.displayName || "Context";
            case REACT_CONSUMER_TYPE:
              return (type._context.displayName || "Context") + ".Consumer";
            case REACT_FORWARD_REF_TYPE:
              var innerType = type.render;
              type = type.displayName;
              type || (type = innerType.displayName || innerType.name || "", type = "" !== type ? "ForwardRef(" + type + ")" : "ForwardRef");
              return type;
            case REACT_MEMO_TYPE:
              return innerType = type.displayName || null, null !== innerType ? innerType : getComponentNameFromType(type.type) || "Memo";
            case REACT_LAZY_TYPE:
              innerType = type._payload;
              type = type._init;
              try {
                return getComponentNameFromType(type(innerType));
              } catch (x) {
              }
          }
        return null;
      }
      function getTaskName(type) {
        if (type === REACT_FRAGMENT_TYPE) return "<>";
        if ("object" === typeof type && null !== type && type.$$typeof === REACT_LAZY_TYPE)
          return "<...>";
        try {
          var name = getComponentNameFromType(type);
          return name ? "<" + name + ">" : "<...>";
        } catch (x) {
          return "<...>";
        }
      }
      function getOwner() {
        var dispatcher = ReactSharedInternals.A;
        return null === dispatcher ? null : dispatcher.getOwner();
      }
      function UnknownOwner() {
        return Error("react-stack-top-frame");
      }
      function hasValidKey(config) {
        if (hasOwnProperty.call(config, "key")) {
          var getter = Object.getOwnPropertyDescriptor(config, "key").get;
          if (getter && getter.isReactWarning) return false;
        }
        return void 0 !== config.key;
      }
      function defineKeyPropWarningGetter(props, displayName) {
        function warnAboutAccessingKey() {
          specialPropKeyWarningShown || (specialPropKeyWarningShown = true, console.error(
            "%s: `key` is not a prop. Trying to access it will result in `undefined` being returned. If you need to access the same value within the child component, you should pass it as a different prop. (https://react.dev/link/special-props)",
            displayName
          ));
        }
        warnAboutAccessingKey.isReactWarning = true;
        Object.defineProperty(props, "key", {
          get: warnAboutAccessingKey,
          configurable: true
        });
      }
      function elementRefGetterWithDeprecationWarning() {
        var componentName = getComponentNameFromType(this.type);
        didWarnAboutElementRef[componentName] || (didWarnAboutElementRef[componentName] = true, console.error(
          "Accessing element.ref was removed in React 19. ref is now a regular prop. It will be removed from the JSX Element type in a future release."
        ));
        componentName = this.props.ref;
        return void 0 !== componentName ? componentName : null;
      }
      function ReactElement(type, key, props, owner, debugStack, debugTask) {
        var refProp = props.ref;
        type = {
          $$typeof: REACT_ELEMENT_TYPE,
          type,
          key,
          props,
          _owner: owner
        };
        null !== (void 0 !== refProp ? refProp : null) ? Object.defineProperty(type, "ref", {
          enumerable: false,
          get: elementRefGetterWithDeprecationWarning
        }) : Object.defineProperty(type, "ref", { enumerable: false, value: null });
        type._store = {};
        Object.defineProperty(type._store, "validated", {
          configurable: false,
          enumerable: false,
          writable: true,
          value: 0
        });
        Object.defineProperty(type, "_debugInfo", {
          configurable: false,
          enumerable: false,
          writable: true,
          value: null
        });
        Object.defineProperty(type, "_debugStack", {
          configurable: false,
          enumerable: false,
          writable: true,
          value: debugStack
        });
        Object.defineProperty(type, "_debugTask", {
          configurable: false,
          enumerable: false,
          writable: true,
          value: debugTask
        });
        Object.freeze && (Object.freeze(type.props), Object.freeze(type));
        return type;
      }
      function cloneAndReplaceKey(oldElement, newKey) {
        newKey = ReactElement(
          oldElement.type,
          newKey,
          oldElement.props,
          oldElement._owner,
          oldElement._debugStack,
          oldElement._debugTask
        );
        oldElement._store && (newKey._store.validated = oldElement._store.validated);
        return newKey;
      }
      function validateChildKeys(node) {
        isValidElement(node) ? node._store && (node._store.validated = 1) : "object" === typeof node && null !== node && node.$$typeof === REACT_LAZY_TYPE && ("fulfilled" === node._payload.status ? isValidElement(node._payload.value) && node._payload.value._store && (node._payload.value._store.validated = 1) : node._store && (node._store.validated = 1));
      }
      function isValidElement(object) {
        return "object" === typeof object && null !== object && object.$$typeof === REACT_ELEMENT_TYPE;
      }
      function escape(key) {
        var escaperLookup = { "=": "=0", ":": "=2" };
        return "$" + key.replace(/[=:]/g, function(match) {
          return escaperLookup[match];
        });
      }
      function getElementKey(element, index) {
        return "object" === typeof element && null !== element && null != element.key ? (checkKeyStringCoercion(element.key), escape("" + element.key)) : index.toString(36);
      }
      function resolveThenable(thenable) {
        switch (thenable.status) {
          case "fulfilled":
            return thenable.value;
          case "rejected":
            throw thenable.reason;
          default:
            switch ("string" === typeof thenable.status ? thenable.then(noop, noop) : (thenable.status = "pending", thenable.then(
              function(fulfilledValue) {
                "pending" === thenable.status && (thenable.status = "fulfilled", thenable.value = fulfilledValue);
              },
              function(error) {
                "pending" === thenable.status && (thenable.status = "rejected", thenable.reason = error);
              }
            )), thenable.status) {
              case "fulfilled":
                return thenable.value;
              case "rejected":
                throw thenable.reason;
            }
        }
        throw thenable;
      }
      function mapIntoArray(children, array, escapedPrefix, nameSoFar, callback) {
        var type = typeof children;
        if ("undefined" === type || "boolean" === type) children = null;
        var invokeCallback = false;
        if (null === children) invokeCallback = true;
        else
          switch (type) {
            case "bigint":
            case "string":
            case "number":
              invokeCallback = true;
              break;
            case "object":
              switch (children.$$typeof) {
                case REACT_ELEMENT_TYPE:
                case REACT_PORTAL_TYPE:
                  invokeCallback = true;
                  break;
                case REACT_LAZY_TYPE:
                  return invokeCallback = children._init, mapIntoArray(
                    invokeCallback(children._payload),
                    array,
                    escapedPrefix,
                    nameSoFar,
                    callback
                  );
              }
          }
        if (invokeCallback) {
          invokeCallback = children;
          callback = callback(invokeCallback);
          var childKey = "" === nameSoFar ? "." + getElementKey(invokeCallback, 0) : nameSoFar;
          isArrayImpl(callback) ? (escapedPrefix = "", null != childKey && (escapedPrefix = childKey.replace(userProvidedKeyEscapeRegex, "$&/") + "/"), mapIntoArray(callback, array, escapedPrefix, "", function(c) {
            return c;
          })) : null != callback && (isValidElement(callback) && (null != callback.key && (invokeCallback && invokeCallback.key === callback.key || checkKeyStringCoercion(callback.key)), escapedPrefix = cloneAndReplaceKey(
            callback,
            escapedPrefix + (null == callback.key || invokeCallback && invokeCallback.key === callback.key ? "" : ("" + callback.key).replace(
              userProvidedKeyEscapeRegex,
              "$&/"
            ) + "/") + childKey
          ), "" !== nameSoFar && null != invokeCallback && isValidElement(invokeCallback) && null == invokeCallback.key && invokeCallback._store && !invokeCallback._store.validated && (escapedPrefix._store.validated = 2), callback = escapedPrefix), array.push(callback));
          return 1;
        }
        invokeCallback = 0;
        childKey = "" === nameSoFar ? "." : nameSoFar + ":";
        if (isArrayImpl(children))
          for (var i = 0; i < children.length; i++)
            nameSoFar = children[i], type = childKey + getElementKey(nameSoFar, i), invokeCallback += mapIntoArray(
              nameSoFar,
              array,
              escapedPrefix,
              type,
              callback
            );
        else if (i = getIteratorFn(children), "function" === typeof i)
          for (i === children.entries && (didWarnAboutMaps || console.warn(
            "Using Maps as children is not supported. Use an array of keyed ReactElements instead."
          ), didWarnAboutMaps = true), children = i.call(children), i = 0; !(nameSoFar = children.next()).done; )
            nameSoFar = nameSoFar.value, type = childKey + getElementKey(nameSoFar, i++), invokeCallback += mapIntoArray(
              nameSoFar,
              array,
              escapedPrefix,
              type,
              callback
            );
        else if ("object" === type) {
          if ("function" === typeof children.then)
            return mapIntoArray(
              resolveThenable(children),
              array,
              escapedPrefix,
              nameSoFar,
              callback
            );
          array = String(children);
          throw Error(
            "Objects are not valid as a React child (found: " + ("[object Object]" === array ? "object with keys {" + Object.keys(children).join(", ") + "}" : array) + "). If you meant to render a collection of children, use an array instead."
          );
        }
        return invokeCallback;
      }
      function mapChildren(children, func, context) {
        if (null == children) return children;
        var result = [], count = 0;
        mapIntoArray(children, result, "", "", function(child) {
          return func.call(context, child, count++);
        });
        return result;
      }
      function lazyInitializer(payload) {
        if (-1 === payload._status) {
          var resolveDebugValue = null, rejectDebugValue = null, ioInfo = payload._ioInfo;
          null != ioInfo && (ioInfo.start = ioInfo.end = performance.now(), ioInfo.value = new Promise(function(resolve, reject) {
            resolveDebugValue = resolve;
            rejectDebugValue = reject;
          }));
          ioInfo = payload._result;
          var thenable = ioInfo();
          thenable.then(
            function(moduleObject) {
              if (0 === payload._status || -1 === payload._status) {
                payload._status = 1;
                payload._result = moduleObject;
                var _ioInfo = payload._ioInfo;
                if (null != _ioInfo) {
                  _ioInfo.end = performance.now();
                  var debugValue = null == moduleObject ? void 0 : moduleObject.default;
                  resolveDebugValue(debugValue);
                  _ioInfo.value.status = "fulfilled";
                  _ioInfo.value.value = debugValue;
                }
                void 0 === thenable.status && (thenable.status = "fulfilled", thenable.value = moduleObject);
              }
            },
            function(error) {
              if (0 === payload._status || -1 === payload._status) {
                payload._status = 2;
                payload._result = error;
                var _ioInfo2 = payload._ioInfo;
                null != _ioInfo2 && (_ioInfo2.end = performance.now(), _ioInfo2.value.then(noop, noop), rejectDebugValue(error), _ioInfo2.value.status = "rejected", _ioInfo2.value.reason = error);
                void 0 === thenable.status && (thenable.status = "rejected", thenable.reason = error);
              }
            }
          );
          ioInfo = payload._ioInfo;
          if (null != ioInfo) {
            var displayName = thenable.displayName;
            "string" === typeof displayName && (ioInfo.name = displayName);
          }
          -1 === payload._status && (payload._status = 0, payload._result = thenable);
        }
        if (1 === payload._status)
          return ioInfo = payload._result, void 0 === ioInfo && console.error(
            "lazy: Expected the result of a dynamic import() call. Instead received: %s\n\nYour code should look like: \n  const MyComponent = lazy(() => import('./MyComponent'))\n\nDid you accidentally put curly braces around the import?",
            ioInfo
          ), "default" in ioInfo || console.error(
            "lazy: Expected the result of a dynamic import() call. Instead received: %s\n\nYour code should look like: \n  const MyComponent = lazy(() => import('./MyComponent'))",
            ioInfo
          ), ioInfo.default;
        throw payload._result;
      }
      function resolveDispatcher() {
        var dispatcher = ReactSharedInternals.H;
        null === dispatcher && console.error(
          "Invalid hook call. Hooks can only be called inside of the body of a function component. This could happen for one of the following reasons:\n1. You might have mismatching versions of React and the renderer (such as React DOM)\n2. You might be breaking the Rules of Hooks\n3. You might have more than one copy of React in the same app\nSee https://react.dev/link/invalid-hook-call for tips about how to debug and fix this problem."
        );
        return dispatcher;
      }
      function releaseAsyncTransition() {
        ReactSharedInternals.asyncTransitions--;
      }
      function startTransition(scope) {
        var prevTransition = ReactSharedInternals.T, currentTransition = {};
        currentTransition.types = null !== prevTransition ? prevTransition.types : null;
        currentTransition._updatedFibers = /* @__PURE__ */ new Set();
        ReactSharedInternals.T = currentTransition;
        try {
          var returnValue = scope(), onStartTransitionFinish = ReactSharedInternals.S;
          null !== onStartTransitionFinish && onStartTransitionFinish(currentTransition, returnValue);
          "object" === typeof returnValue && null !== returnValue && "function" === typeof returnValue.then && (ReactSharedInternals.asyncTransitions++, returnValue.then(releaseAsyncTransition, releaseAsyncTransition), returnValue.then(noop, reportGlobalError));
        } catch (error) {
          reportGlobalError(error);
        } finally {
          null === prevTransition && currentTransition._updatedFibers && (scope = currentTransition._updatedFibers.size, currentTransition._updatedFibers.clear(), 10 < scope && console.warn(
            "Detected a large number of updates inside startTransition. If this is due to a subscription please re-write it to use React provided hooks. Otherwise concurrent mode guarantees are off the table."
          )), null !== prevTransition && null !== currentTransition.types && (null !== prevTransition.types && prevTransition.types !== currentTransition.types && console.error(
            "We expected inner Transitions to have transferred the outer types set and that you cannot add to the outer Transition while inside the inner.This is a bug in React."
          ), prevTransition.types = currentTransition.types), ReactSharedInternals.T = prevTransition;
        }
      }
      function addTransitionType(type) {
        var transition = ReactSharedInternals.T;
        if (null !== transition) {
          var transitionTypes = transition.types;
          null === transitionTypes ? transition.types = [type] : -1 === transitionTypes.indexOf(type) && transitionTypes.push(type);
        } else
          0 === ReactSharedInternals.asyncTransitions && console.error(
            "addTransitionType can only be called inside a `startTransition()` callback. It must be associated with a specific Transition."
          ), startTransition(addTransitionType.bind(null, type));
      }
      function enqueueTask(task) {
        if (null === enqueueTaskImpl)
          try {
            var requireString = ("require" + Math.random()).slice(0, 7);
            enqueueTaskImpl = (module && module[requireString]).call(
              module,
              "timers"
            ).setImmediate;
          } catch (_err) {
            enqueueTaskImpl = function(callback) {
              false === didWarnAboutMessageChannel && (didWarnAboutMessageChannel = true, "undefined" === typeof MessageChannel && console.error(
                "This browser does not have a MessageChannel implementation, so enqueuing tasks via await act(async () => ...) will fail. Please file an issue at https://github.com/facebook/react/issues if you encounter this warning."
              ));
              var channel = new MessageChannel();
              channel.port1.onmessage = callback;
              channel.port2.postMessage(void 0);
            };
          }
        return enqueueTaskImpl(task);
      }
      function aggregateErrors(errors) {
        return 1 < errors.length && "function" === typeof AggregateError ? new AggregateError(errors) : errors[0];
      }
      function popActScope(prevActQueue, prevActScopeDepth) {
        prevActScopeDepth !== actScopeDepth - 1 && console.error(
          "You seem to have overlapping act() calls, this is not supported. Be sure to await previous act() calls before making a new one. "
        );
        actScopeDepth = prevActScopeDepth;
      }
      function recursivelyFlushAsyncActWork(returnValue, resolve, reject) {
        var queue = ReactSharedInternals.actQueue;
        if (null !== queue)
          if (0 !== queue.length)
            try {
              flushActQueue(queue);
              enqueueTask(function() {
                return recursivelyFlushAsyncActWork(returnValue, resolve, reject);
              });
              return;
            } catch (error) {
              ReactSharedInternals.thrownErrors.push(error);
            }
          else ReactSharedInternals.actQueue = null;
        0 < ReactSharedInternals.thrownErrors.length ? (queue = aggregateErrors(ReactSharedInternals.thrownErrors), ReactSharedInternals.thrownErrors.length = 0, reject(queue)) : resolve(returnValue);
      }
      function flushActQueue(queue) {
        if (!isFlushing) {
          isFlushing = true;
          var i = 0;
          try {
            for (; i < queue.length; i++) {
              var callback = queue[i];
              do {
                ReactSharedInternals.didUsePromise = false;
                var continuation = callback(false);
                if (null !== continuation) {
                  if (ReactSharedInternals.didUsePromise) {
                    queue[i] = callback;
                    queue.splice(0, i);
                    return;
                  }
                  callback = continuation;
                } else break;
              } while (1);
            }
            queue.length = 0;
          } catch (error) {
            queue.splice(0, i + 1), ReactSharedInternals.thrownErrors.push(error);
          } finally {
            isFlushing = false;
          }
        }
      }
      "undefined" !== typeof __REACT_DEVTOOLS_GLOBAL_HOOK__ && "function" === typeof __REACT_DEVTOOLS_GLOBAL_HOOK__.registerInternalModuleStart && __REACT_DEVTOOLS_GLOBAL_HOOK__.registerInternalModuleStart(Error());
      var REACT_ELEMENT_TYPE = Symbol.for("react.transitional.element"), REACT_PORTAL_TYPE = Symbol.for("react.portal"), REACT_FRAGMENT_TYPE = Symbol.for("react.fragment"), REACT_STRICT_MODE_TYPE = Symbol.for("react.strict_mode"), REACT_PROFILER_TYPE = Symbol.for("react.profiler"), REACT_CONSUMER_TYPE = Symbol.for("react.consumer"), REACT_CONTEXT_TYPE = Symbol.for("react.context"), REACT_FORWARD_REF_TYPE = Symbol.for("react.forward_ref"), REACT_SUSPENSE_TYPE = Symbol.for("react.suspense"), REACT_SUSPENSE_LIST_TYPE = Symbol.for("react.suspense_list"), REACT_MEMO_TYPE = Symbol.for("react.memo"), REACT_LAZY_TYPE = Symbol.for("react.lazy"), REACT_ACTIVITY_TYPE = Symbol.for("react.activity"), REACT_VIEW_TRANSITION_TYPE = Symbol.for("react.view_transition"), MAYBE_ITERATOR_SYMBOL = Symbol.iterator, didWarnStateUpdateForUnmountedComponent = {}, ReactNoopUpdateQueue = {
        isMounted: function() {
          return false;
        },
        enqueueForceUpdate: function(publicInstance) {
          warnNoop(publicInstance, "forceUpdate");
        },
        enqueueReplaceState: function(publicInstance) {
          warnNoop(publicInstance, "replaceState");
        },
        enqueueSetState: function(publicInstance) {
          warnNoop(publicInstance, "setState");
        }
      }, assign = Object.assign, emptyObject = {};
      Object.freeze(emptyObject);
      Component.prototype.isReactComponent = {};
      Component.prototype.setState = function(partialState, callback) {
        if ("object" !== typeof partialState && "function" !== typeof partialState && null != partialState)
          throw Error(
            "takes an object of state variables to update or a function which returns an object of state variables."
          );
        this.updater.enqueueSetState(this, partialState, callback, "setState");
      };
      Component.prototype.forceUpdate = function(callback) {
        this.updater.enqueueForceUpdate(this, callback, "forceUpdate");
      };
      var deprecatedAPIs = {
        isMounted: [
          "isMounted",
          "Instead, make sure to clean up subscriptions and pending requests in componentWillUnmount to prevent memory leaks."
        ],
        replaceState: [
          "replaceState",
          "Refactor your code to use setState instead (see https://github.com/facebook/react/issues/3236)."
        ]
      };
      for (fnName in deprecatedAPIs)
        deprecatedAPIs.hasOwnProperty(fnName) && defineDeprecationWarning(fnName, deprecatedAPIs[fnName]);
      ComponentDummy.prototype = Component.prototype;
      deprecatedAPIs = PureComponent.prototype = new ComponentDummy();
      deprecatedAPIs.constructor = PureComponent;
      assign(deprecatedAPIs, Component.prototype);
      deprecatedAPIs.isPureReactComponent = true;
      var isArrayImpl = Array.isArray, REACT_CLIENT_REFERENCE = Symbol.for("react.client.reference"), ReactSharedInternals = {
        H: null,
        A: null,
        T: null,
        S: null,
        actQueue: null,
        asyncTransitions: 0,
        isBatchingLegacy: false,
        didScheduleLegacyUpdate: false,
        didUsePromise: false,
        thrownErrors: [],
        getCurrentStack: null,
        recentlyCreatedOwnerStacks: 0
      }, hasOwnProperty = Object.prototype.hasOwnProperty, createTask = console.createTask ? console.createTask : function() {
        return null;
      };
      deprecatedAPIs = {
        react_stack_bottom_frame: function(callStackForError) {
          return callStackForError();
        }
      };
      var specialPropKeyWarningShown, didWarnAboutOldJSXRuntime;
      var didWarnAboutElementRef = {};
      var unknownOwnerDebugStack = deprecatedAPIs.react_stack_bottom_frame.bind(
        deprecatedAPIs,
        UnknownOwner
      )();
      var unknownOwnerDebugTask = createTask(getTaskName(UnknownOwner));
      var didWarnAboutMaps = false, userProvidedKeyEscapeRegex = /\/+/g, reportGlobalError = "function" === typeof reportError ? reportError : function(error) {
        if ("object" === typeof window && "function" === typeof window.ErrorEvent) {
          var event = new window.ErrorEvent("error", {
            bubbles: true,
            cancelable: true,
            message: "object" === typeof error && null !== error && "string" === typeof error.message ? String(error.message) : String(error),
            error
          });
          if (!window.dispatchEvent(event)) return;
        } else if ("object" === typeof process && "function" === typeof process.emit) {
          process.emit("uncaughtException", error);
          return;
        }
        console.error(error);
      }, didWarnAboutMessageChannel = false, enqueueTaskImpl = null, actScopeDepth = 0, didWarnNoAwaitAct = false, isFlushing = false, queueSeveralMicrotasks = "function" === typeof queueMicrotask ? function(callback) {
        queueMicrotask(function() {
          return queueMicrotask(callback);
        });
      } : enqueueTask;
      deprecatedAPIs = Object.freeze({
        __proto__: null,
        c: function(size) {
          return resolveDispatcher().useMemoCache(size);
        }
      });
      var fnName = {
        map: mapChildren,
        forEach: function(children, forEachFunc, forEachContext) {
          mapChildren(
            children,
            function() {
              forEachFunc.apply(this, arguments);
            },
            forEachContext
          );
        },
        count: function(children) {
          var n = 0;
          mapChildren(children, function() {
            n++;
          });
          return n;
        },
        toArray: function(children) {
          return mapChildren(children, function(child) {
            return child;
          }) || [];
        },
        only: function(children) {
          if (!isValidElement(children))
            throw Error(
              "React.Children.only expected to receive a single React element child."
            );
          return children;
        }
      };
      exports.Activity = REACT_ACTIVITY_TYPE;
      exports.Children = fnName;
      exports.Component = Component;
      exports.Fragment = REACT_FRAGMENT_TYPE;
      exports.Profiler = REACT_PROFILER_TYPE;
      exports.PureComponent = PureComponent;
      exports.StrictMode = REACT_STRICT_MODE_TYPE;
      exports.Suspense = REACT_SUSPENSE_TYPE;
      exports.ViewTransition = REACT_VIEW_TRANSITION_TYPE;
      exports.__CLIENT_INTERNALS_DO_NOT_USE_OR_WARN_USERS_THEY_CANNOT_UPGRADE = ReactSharedInternals;
      exports.__COMPILER_RUNTIME = deprecatedAPIs;
      exports.act = function(callback) {
        var prevActQueue = ReactSharedInternals.actQueue, prevActScopeDepth = actScopeDepth;
        actScopeDepth++;
        var queue = ReactSharedInternals.actQueue = null !== prevActQueue ? prevActQueue : [], didAwaitActCall = false;
        try {
          var result = callback();
        } catch (error) {
          ReactSharedInternals.thrownErrors.push(error);
        }
        if (0 < ReactSharedInternals.thrownErrors.length)
          throw popActScope(prevActQueue, prevActScopeDepth), callback = aggregateErrors(ReactSharedInternals.thrownErrors), ReactSharedInternals.thrownErrors.length = 0, callback;
        if (null !== result && "object" === typeof result && "function" === typeof result.then) {
          var thenable = result;
          queueSeveralMicrotasks(function() {
            didAwaitActCall || didWarnNoAwaitAct || (didWarnNoAwaitAct = true, console.error(
              "You called act(async () => ...) without await. This could lead to unexpected testing behaviour, interleaving multiple act calls and mixing their scopes. You should - await act(async () => ...);"
            ));
          });
          return {
            then: function(resolve, reject) {
              didAwaitActCall = true;
              thenable.then(
                function(returnValue) {
                  popActScope(prevActQueue, prevActScopeDepth);
                  if (0 === prevActScopeDepth) {
                    try {
                      flushActQueue(queue), enqueueTask(function() {
                        return recursivelyFlushAsyncActWork(
                          returnValue,
                          resolve,
                          reject
                        );
                      });
                    } catch (error$0) {
                      ReactSharedInternals.thrownErrors.push(error$0);
                    }
                    if (0 < ReactSharedInternals.thrownErrors.length) {
                      var _thrownError = aggregateErrors(
                        ReactSharedInternals.thrownErrors
                      );
                      ReactSharedInternals.thrownErrors.length = 0;
                      reject(_thrownError);
                    }
                  } else resolve(returnValue);
                },
                function(error) {
                  popActScope(prevActQueue, prevActScopeDepth);
                  0 < ReactSharedInternals.thrownErrors.length ? (error = aggregateErrors(
                    ReactSharedInternals.thrownErrors
                  ), ReactSharedInternals.thrownErrors.length = 0, reject(error)) : reject(error);
                }
              );
            }
          };
        }
        var returnValue$jscomp$0 = result;
        popActScope(prevActQueue, prevActScopeDepth);
        0 === prevActScopeDepth && (flushActQueue(queue), 0 !== queue.length && queueSeveralMicrotasks(function() {
          didAwaitActCall || didWarnNoAwaitAct || (didWarnNoAwaitAct = true, console.error(
            "A component suspended inside an `act` scope, but the `act` call was not awaited. When testing React components that depend on asynchronous data, you must await the result:\n\nawait act(() => ...)"
          ));
        }), ReactSharedInternals.actQueue = null);
        if (0 < ReactSharedInternals.thrownErrors.length)
          throw callback = aggregateErrors(ReactSharedInternals.thrownErrors), ReactSharedInternals.thrownErrors.length = 0, callback;
        return {
          then: function(resolve, reject) {
            didAwaitActCall = true;
            0 === prevActScopeDepth ? (ReactSharedInternals.actQueue = queue, enqueueTask(function() {
              return recursivelyFlushAsyncActWork(
                returnValue$jscomp$0,
                resolve,
                reject
              );
            })) : resolve(returnValue$jscomp$0);
          }
        };
      };
      exports.addTransitionType = addTransitionType;
      exports.cache = function(fn) {
        return function() {
          return fn.apply(null, arguments);
        };
      };
      exports.cacheSignal = function() {
        return null;
      };
      exports.captureOwnerStack = function() {
        var getCurrentStack = ReactSharedInternals.getCurrentStack;
        return null === getCurrentStack ? null : getCurrentStack();
      };
      exports.cloneElement = function(element, config, children) {
        if (null === element || void 0 === element)
          throw Error(
            "The argument must be a React element, but you passed " + element + "."
          );
        var props = assign({}, element.props), key = element.key, owner = element._owner;
        if (null != config) {
          var JSCompiler_inline_result;
          a: {
            if (hasOwnProperty.call(config, "ref") && (JSCompiler_inline_result = Object.getOwnPropertyDescriptor(
              config,
              "ref"
            ).get) && JSCompiler_inline_result.isReactWarning) {
              JSCompiler_inline_result = false;
              break a;
            }
            JSCompiler_inline_result = void 0 !== config.ref;
          }
          JSCompiler_inline_result && (owner = getOwner());
          hasValidKey(config) && (checkKeyStringCoercion(config.key), key = "" + config.key);
          for (propName in config)
            !hasOwnProperty.call(config, propName) || "key" === propName || "__self" === propName || "__source" === propName || "ref" === propName && void 0 === config.ref || (props[propName] = config[propName]);
        }
        var propName = arguments.length - 2;
        if (1 === propName) props.children = children;
        else if (1 < propName) {
          JSCompiler_inline_result = Array(propName);
          for (var i = 0; i < propName; i++)
            JSCompiler_inline_result[i] = arguments[i + 2];
          props.children = JSCompiler_inline_result;
        }
        props = ReactElement(
          element.type,
          key,
          props,
          owner,
          element._debugStack,
          element._debugTask
        );
        for (key = 2; key < arguments.length; key++)
          validateChildKeys(arguments[key]);
        return props;
      };
      exports.createContext = function(defaultValue) {
        defaultValue = {
          $$typeof: REACT_CONTEXT_TYPE,
          _currentValue: defaultValue,
          _currentValue2: defaultValue,
          _threadCount: 0,
          Provider: null,
          Consumer: null
        };
        defaultValue.Provider = defaultValue;
        defaultValue.Consumer = {
          $$typeof: REACT_CONSUMER_TYPE,
          _context: defaultValue
        };
        defaultValue._currentRenderer = null;
        defaultValue._currentRenderer2 = null;
        return defaultValue;
      };
      exports.createElement = function(type, config, children) {
        for (var i = 2; i < arguments.length; i++)
          validateChildKeys(arguments[i]);
        var propName;
        i = {};
        var key = null;
        if (null != config)
          for (propName in didWarnAboutOldJSXRuntime || !("__self" in config) || "key" in config || (didWarnAboutOldJSXRuntime = true, console.warn(
            "Your app (or one of its dependencies) is using an outdated JSX transform. Update to the modern JSX transform for faster performance: https://react.dev/link/new-jsx-transform"
          )), hasValidKey(config) && (checkKeyStringCoercion(config.key), key = "" + config.key), config)
            hasOwnProperty.call(config, propName) && "key" !== propName && "__self" !== propName && "__source" !== propName && (i[propName] = config[propName]);
        var childrenLength = arguments.length - 2;
        if (1 === childrenLength) i.children = children;
        else if (1 < childrenLength) {
          for (var childArray = Array(childrenLength), _i = 0; _i < childrenLength; _i++)
            childArray[_i] = arguments[_i + 2];
          Object.freeze && Object.freeze(childArray);
          i.children = childArray;
        }
        if (type && type.defaultProps)
          for (propName in childrenLength = type.defaultProps, childrenLength)
            void 0 === i[propName] && (i[propName] = childrenLength[propName]);
        key && defineKeyPropWarningGetter(
          i,
          "function" === typeof type ? type.displayName || type.name || "Unknown" : type
        );
        (propName = 1e4 > ReactSharedInternals.recentlyCreatedOwnerStacks++) ? (childArray = Error.stackTraceLimit, Error.stackTraceLimit = 10, childrenLength = Error("react-stack-top-frame"), Error.stackTraceLimit = childArray) : childrenLength = unknownOwnerDebugStack;
        return ReactElement(
          type,
          key,
          i,
          getOwner(),
          childrenLength,
          propName ? createTask(getTaskName(type)) : unknownOwnerDebugTask
        );
      };
      exports.createRef = function() {
        var refObject = { current: null };
        Object.seal(refObject);
        return refObject;
      };
      exports.forwardRef = function(render) {
        null != render && render.$$typeof === REACT_MEMO_TYPE ? console.error(
          "forwardRef requires a render function but received a `memo` component. Instead of forwardRef(memo(...)), use memo(forwardRef(...))."
        ) : "function" !== typeof render ? console.error(
          "forwardRef requires a render function but was given %s.",
          null === render ? "null" : typeof render
        ) : 0 !== render.length && 2 !== render.length && console.error(
          "forwardRef render functions accept exactly two parameters: props and ref. %s",
          1 === render.length ? "Did you forget to use the ref parameter?" : "Any additional parameter will be undefined."
        );
        null != render && null != render.defaultProps && console.error(
          "forwardRef render functions do not support defaultProps. Did you accidentally pass a React component?"
        );
        var elementType = { $$typeof: REACT_FORWARD_REF_TYPE, render }, ownName;
        Object.defineProperty(elementType, "displayName", {
          enumerable: false,
          configurable: true,
          get: function() {
            return ownName;
          },
          set: function(name) {
            ownName = name;
            render.name || render.displayName || (Object.defineProperty(render, "name", { value: name }), render.displayName = name);
          }
        });
        return elementType;
      };
      exports.isValidElement = isValidElement;
      exports.lazy = function(ctor) {
        ctor = { _status: -1, _result: ctor };
        var lazyType = {
          $$typeof: REACT_LAZY_TYPE,
          _payload: ctor,
          _init: lazyInitializer
        }, ioInfo = {
          name: "lazy",
          start: -1,
          end: -1,
          value: null,
          owner: null,
          debugStack: Error("react-stack-top-frame"),
          debugTask: console.createTask ? console.createTask("lazy()") : null
        };
        ctor._ioInfo = ioInfo;
        lazyType._debugInfo = [{ awaited: ioInfo }];
        return lazyType;
      };
      exports.memo = function(type, compare) {
        null == type && console.error(
          "memo: The first argument must be a component. Instead received: %s",
          null === type ? "null" : typeof type
        );
        compare = {
          $$typeof: REACT_MEMO_TYPE,
          type,
          compare: void 0 === compare ? null : compare
        };
        var ownName;
        Object.defineProperty(compare, "displayName", {
          enumerable: false,
          configurable: true,
          get: function() {
            return ownName;
          },
          set: function(name) {
            ownName = name;
            type.name || type.displayName || (Object.defineProperty(type, "name", { value: name }), type.displayName = name);
          }
        });
        return compare;
      };
      exports.startTransition = startTransition;
      exports.unstable_useCacheRefresh = function() {
        return resolveDispatcher().useCacheRefresh();
      };
      exports.use = function(usable) {
        return resolveDispatcher().use(usable);
      };
      exports.useActionState = function(action, initialState, permalink) {
        return resolveDispatcher().useActionState(
          action,
          initialState,
          permalink
        );
      };
      exports.useCallback = function(callback, deps) {
        return resolveDispatcher().useCallback(callback, deps);
      };
      exports.useContext = function(Context) {
        var dispatcher = resolveDispatcher();
        Context.$$typeof === REACT_CONSUMER_TYPE && console.error(
          "Calling useContext(Context.Consumer) is not supported and will cause bugs. Did you mean to call useContext(Context) instead?"
        );
        return dispatcher.useContext(Context);
      };
      exports.useDebugValue = function(value, formatterFn) {
        return resolveDispatcher().useDebugValue(value, formatterFn);
      };
      exports.useDeferredValue = function(value, initialValue) {
        return resolveDispatcher().useDeferredValue(value, initialValue);
      };
      exports.useEffect = function(create2, deps) {
        null == create2 && console.warn(
          "React Hook useEffect requires an effect callback. Did you forget to pass a callback to the hook?"
        );
        return resolveDispatcher().useEffect(create2, deps);
      };
      exports.useEffectEvent = function(callback) {
        return resolveDispatcher().useEffectEvent(callback);
      };
      exports.useId = function() {
        return resolveDispatcher().useId();
      };
      exports.useImperativeHandle = function(ref, create2, deps) {
        return resolveDispatcher().useImperativeHandle(ref, create2, deps);
      };
      exports.useInsertionEffect = function(create2, deps) {
        null == create2 && console.warn(
          "React Hook useInsertionEffect requires an effect callback. Did you forget to pass a callback to the hook?"
        );
        return resolveDispatcher().useInsertionEffect(create2, deps);
      };
      exports.useLayoutEffect = function(create2, deps) {
        null == create2 && console.warn(
          "React Hook useLayoutEffect requires an effect callback. Did you forget to pass a callback to the hook?"
        );
        return resolveDispatcher().useLayoutEffect(create2, deps);
      };
      exports.useMemo = function(create2, deps) {
        return resolveDispatcher().useMemo(create2, deps);
      };
      exports.useOptimistic = function(passthrough, reducer) {
        return resolveDispatcher().useOptimistic(passthrough, reducer);
      };
      exports.useReducer = function(reducer, initialArg, init) {
        return resolveDispatcher().useReducer(reducer, initialArg, init);
      };
      exports.useRef = function(initialValue) {
        return resolveDispatcher().useRef(initialValue);
      };
      exports.useState = function(initialState) {
        return resolveDispatcher().useState(initialState);
      };
      exports.useSyncExternalStore = function(subscribe, getSnapshot, getServerSnapshot) {
        return resolveDispatcher().useSyncExternalStore(
          subscribe,
          getSnapshot,
          getServerSnapshot
        );
      };
      exports.useTransition = function() {
        return resolveDispatcher().useTransition();
      };
      exports.version = "19.3.1";
      "undefined" !== typeof __REACT_DEVTOOLS_GLOBAL_HOOK__ && "function" === typeof __REACT_DEVTOOLS_GLOBAL_HOOK__.registerInternalModuleStop && __REACT_DEVTOOLS_GLOBAL_HOOK__.registerInternalModuleStop(Error());
    })();
  }
});

// node_modules/react/index.js
var require_react = __commonJS({
  "node_modules/react/index.js"(exports, module) {
    "use strict";
    if (false) {
      module.exports = null;
    } else {
      module.exports = require_react_development();
    }
  }
});

// node_modules/react/cjs/react-jsx-runtime.development.js
var require_react_jsx_runtime_development = __commonJS({
  "node_modules/react/cjs/react-jsx-runtime.development.js"(exports) {
    "use strict";
    (function() {
      function getComponentNameFromType(type) {
        if (null == type) return null;
        if ("function" === typeof type)
          return type.$$typeof === REACT_CLIENT_REFERENCE ? null : type.displayName || type.name || null;
        if ("string" === typeof type) return type;
        switch (type) {
          case REACT_FRAGMENT_TYPE:
            return "Fragment";
          case REACT_PROFILER_TYPE:
            return "Profiler";
          case REACT_STRICT_MODE_TYPE:
            return "StrictMode";
          case REACT_SUSPENSE_TYPE:
            return "Suspense";
          case REACT_SUSPENSE_LIST_TYPE:
            return "SuspenseList";
          case REACT_ACTIVITY_TYPE:
            return "Activity";
          case REACT_VIEW_TRANSITION_TYPE:
            return "ViewTransition";
        }
        if ("object" === typeof type)
          switch ("number" === typeof type.tag && console.error(
            "Received an unexpected object in getComponentNameFromType(). This is likely a bug in React. Please file an issue."
          ), type.$$typeof) {
            case REACT_PORTAL_TYPE:
              return "Portal";
            case REACT_CONTEXT_TYPE:
              return type.displayName || "Context";
            case REACT_CONSUMER_TYPE:
              return (type._context.displayName || "Context") + ".Consumer";
            case REACT_FORWARD_REF_TYPE:
              var innerType = type.render;
              type = type.displayName;
              type || (type = innerType.displayName || innerType.name || "", type = "" !== type ? "ForwardRef(" + type + ")" : "ForwardRef");
              return type;
            case REACT_MEMO_TYPE:
              return innerType = type.displayName || null, null !== innerType ? innerType : getComponentNameFromType(type.type) || "Memo";
            case REACT_LAZY_TYPE:
              innerType = type._payload;
              type = type._init;
              try {
                return getComponentNameFromType(type(innerType));
              } catch (x) {
              }
          }
        return null;
      }
      function testStringCoercion(value) {
        return "" + value;
      }
      function checkKeyStringCoercion(value) {
        try {
          testStringCoercion(value);
          var JSCompiler_inline_result = false;
        } catch (e) {
          JSCompiler_inline_result = true;
        }
        if (JSCompiler_inline_result) {
          JSCompiler_inline_result = console;
          var JSCompiler_temp_const = JSCompiler_inline_result.error;
          var JSCompiler_inline_result$jscomp$0 = "function" === typeof Symbol && Symbol.toStringTag && value[Symbol.toStringTag] || value.constructor.name || "Object";
          JSCompiler_temp_const.call(
            JSCompiler_inline_result,
            "The provided key is an unsupported type %s. This value must be coerced to a string before using it here.",
            JSCompiler_inline_result$jscomp$0
          );
          return testStringCoercion(value);
        }
      }
      function getTaskName(type) {
        if (type === REACT_FRAGMENT_TYPE) return "<>";
        if ("object" === typeof type && null !== type && type.$$typeof === REACT_LAZY_TYPE)
          return "<...>";
        try {
          var name = getComponentNameFromType(type);
          return name ? "<" + name + ">" : "<...>";
        } catch (x) {
          return "<...>";
        }
      }
      function getOwner() {
        var dispatcher = ReactSharedInternals.A;
        return null === dispatcher ? null : dispatcher.getOwner();
      }
      function UnknownOwner() {
        return Error("react-stack-top-frame");
      }
      function hasValidKey(config) {
        if (hasOwnProperty.call(config, "key")) {
          var getter = Object.getOwnPropertyDescriptor(config, "key").get;
          if (getter && getter.isReactWarning) return false;
        }
        return void 0 !== config.key;
      }
      function defineKeyPropWarningGetter(props, displayName) {
        function warnAboutAccessingKey() {
          specialPropKeyWarningShown || (specialPropKeyWarningShown = true, console.error(
            "%s: `key` is not a prop. Trying to access it will result in `undefined` being returned. If you need to access the same value within the child component, you should pass it as a different prop. (https://react.dev/link/special-props)",
            displayName
          ));
        }
        warnAboutAccessingKey.isReactWarning = true;
        Object.defineProperty(props, "key", {
          get: warnAboutAccessingKey,
          configurable: true
        });
      }
      function elementRefGetterWithDeprecationWarning() {
        var componentName = getComponentNameFromType(this.type);
        didWarnAboutElementRef[componentName] || (didWarnAboutElementRef[componentName] = true, console.error(
          "Accessing element.ref was removed in React 19. ref is now a regular prop. It will be removed from the JSX Element type in a future release."
        ));
        componentName = this.props.ref;
        return void 0 !== componentName ? componentName : null;
      }
      function ReactElement(type, key, props, owner, debugStack, debugTask) {
        var refProp = props.ref;
        type = {
          $$typeof: REACT_ELEMENT_TYPE,
          type,
          key,
          props,
          _owner: owner
        };
        null !== (void 0 !== refProp ? refProp : null) ? Object.defineProperty(type, "ref", {
          enumerable: false,
          get: elementRefGetterWithDeprecationWarning
        }) : Object.defineProperty(type, "ref", { enumerable: false, value: null });
        type._store = {};
        Object.defineProperty(type._store, "validated", {
          configurable: false,
          enumerable: false,
          writable: true,
          value: 0
        });
        Object.defineProperty(type, "_debugInfo", {
          configurable: false,
          enumerable: false,
          writable: true,
          value: null
        });
        Object.defineProperty(type, "_debugStack", {
          configurable: false,
          enumerable: false,
          writable: true,
          value: debugStack
        });
        Object.defineProperty(type, "_debugTask", {
          configurable: false,
          enumerable: false,
          writable: true,
          value: debugTask
        });
        Object.freeze && (Object.freeze(type.props), Object.freeze(type));
        return type;
      }
      function jsxDEVImpl(type, config, maybeKey, isStaticChildren, debugStack, debugTask) {
        var children = config.children;
        if (void 0 !== children)
          if (isStaticChildren)
            if (isArrayImpl(children)) {
              for (isStaticChildren = 0; isStaticChildren < children.length; isStaticChildren++)
                validateChildKeys(children[isStaticChildren]);
              Object.freeze && Object.freeze(children);
            } else
              console.error(
                "React.jsx: Static children should always be an array. You are likely explicitly calling React.jsxs or React.jsxDEV. Use the Babel transform instead."
              );
          else validateChildKeys(children);
        if (hasOwnProperty.call(config, "key")) {
          children = getComponentNameFromType(type);
          var keys = Object.keys(config).filter(function(k) {
            return "key" !== k;
          });
          isStaticChildren = 0 < keys.length ? "{key: someKey, " + keys.join(": ..., ") + ": ...}" : "{key: someKey}";
          didWarnAboutKeySpread[children + isStaticChildren] || (keys = 0 < keys.length ? "{" + keys.join(": ..., ") + ": ...}" : "{}", console.error(
            'A props object containing a "key" prop is being spread into JSX:\n  let props = %s;\n  <%s {...props} />\nReact keys must be passed directly to JSX without using spread:\n  let props = %s;\n  <%s key={someKey} {...props} />',
            isStaticChildren,
            children,
            keys,
            children
          ), didWarnAboutKeySpread[children + isStaticChildren] = true);
        }
        children = null;
        void 0 !== maybeKey && (checkKeyStringCoercion(maybeKey), children = "" + maybeKey);
        hasValidKey(config) && (checkKeyStringCoercion(config.key), children = "" + config.key);
        if ("key" in config) {
          maybeKey = {};
          for (var propName in config)
            "key" !== propName && (maybeKey[propName] = config[propName]);
        } else maybeKey = config;
        children && defineKeyPropWarningGetter(
          maybeKey,
          "function" === typeof type ? type.displayName || type.name || "Unknown" : type
        );
        return ReactElement(
          type,
          children,
          maybeKey,
          getOwner(),
          debugStack,
          debugTask
        );
      }
      function validateChildKeys(node) {
        isValidElement(node) ? node._store && (node._store.validated = 1) : "object" === typeof node && null !== node && node.$$typeof === REACT_LAZY_TYPE && ("fulfilled" === node._payload.status ? isValidElement(node._payload.value) && node._payload.value._store && (node._payload.value._store.validated = 1) : node._store && (node._store.validated = 1));
      }
      function isValidElement(object) {
        return "object" === typeof object && null !== object && object.$$typeof === REACT_ELEMENT_TYPE;
      }
      var React2 = require_react(), REACT_ELEMENT_TYPE = Symbol.for("react.transitional.element"), REACT_PORTAL_TYPE = Symbol.for("react.portal"), REACT_FRAGMENT_TYPE = Symbol.for("react.fragment"), REACT_STRICT_MODE_TYPE = Symbol.for("react.strict_mode"), REACT_PROFILER_TYPE = Symbol.for("react.profiler"), REACT_CONSUMER_TYPE = Symbol.for("react.consumer"), REACT_CONTEXT_TYPE = Symbol.for("react.context"), REACT_FORWARD_REF_TYPE = Symbol.for("react.forward_ref"), REACT_SUSPENSE_TYPE = Symbol.for("react.suspense"), REACT_SUSPENSE_LIST_TYPE = Symbol.for("react.suspense_list"), REACT_MEMO_TYPE = Symbol.for("react.memo"), REACT_LAZY_TYPE = Symbol.for("react.lazy"), REACT_ACTIVITY_TYPE = Symbol.for("react.activity"), REACT_VIEW_TRANSITION_TYPE = Symbol.for("react.view_transition"), REACT_CLIENT_REFERENCE = Symbol.for("react.client.reference"), ReactSharedInternals = React2.__CLIENT_INTERNALS_DO_NOT_USE_OR_WARN_USERS_THEY_CANNOT_UPGRADE, hasOwnProperty = Object.prototype.hasOwnProperty, isArrayImpl = Array.isArray, createTask = console.createTask ? console.createTask : function() {
        return null;
      };
      React2 = {
        react_stack_bottom_frame: function(callStackForError) {
          return callStackForError();
        }
      };
      var specialPropKeyWarningShown;
      var didWarnAboutElementRef = {};
      var unknownOwnerDebugStack = React2.react_stack_bottom_frame.bind(
        React2,
        UnknownOwner
      )();
      var unknownOwnerDebugTask = createTask(getTaskName(UnknownOwner));
      var didWarnAboutKeySpread = {};
      exports.Fragment = REACT_FRAGMENT_TYPE;
      exports.jsx = function(type, config, maybeKey) {
        var trackActualOwner = 1e4 > ReactSharedInternals.recentlyCreatedOwnerStacks++;
        if (trackActualOwner) {
          var previousStackTraceLimit = Error.stackTraceLimit;
          Error.stackTraceLimit = 10;
          var debugStackDEV = Error("react-stack-top-frame");
          Error.stackTraceLimit = previousStackTraceLimit;
        } else debugStackDEV = unknownOwnerDebugStack;
        return jsxDEVImpl(
          type,
          config,
          maybeKey,
          false,
          debugStackDEV,
          trackActualOwner ? createTask(getTaskName(type)) : unknownOwnerDebugTask
        );
      };
      exports.jsxs = function(type, config, maybeKey) {
        var trackActualOwner = 1e4 > ReactSharedInternals.recentlyCreatedOwnerStacks++;
        if (trackActualOwner) {
          var previousStackTraceLimit = Error.stackTraceLimit;
          Error.stackTraceLimit = 10;
          var debugStackDEV = Error("react-stack-top-frame");
          Error.stackTraceLimit = previousStackTraceLimit;
        } else debugStackDEV = unknownOwnerDebugStack;
        return jsxDEVImpl(
          type,
          config,
          maybeKey,
          true,
          debugStackDEV,
          trackActualOwner ? createTask(getTaskName(type)) : unknownOwnerDebugTask
        );
      };
    })();
  }
});

// node_modules/react/jsx-runtime.js
var require_jsx_runtime = __commonJS({
  "node_modules/react/jsx-runtime.js"(exports, module) {
    "use strict";
    if (false) {
      module.exports = null;
    } else {
      module.exports = require_react_jsx_runtime_development();
    }
  }
});

// node_modules/scheduler/cjs/scheduler.development.js
var require_scheduler_development = __commonJS({
  "node_modules/scheduler/cjs/scheduler.development.js"(exports) {
    "use strict";
    (function() {
      function performWorkUntilDeadline() {
        needsPaint = false;
        if (isMessageLoopRunning) {
          var currentTime = exports.unstable_now();
          startTime = currentTime;
          var hasMoreWork = true;
          try {
            a: {
              isHostCallbackScheduled = false;
              isHostTimeoutScheduled && (isHostTimeoutScheduled = false, localClearTimeout(taskTimeoutID), taskTimeoutID = -1);
              isPerformingWork = true;
              var previousPriorityLevel = currentPriorityLevel;
              try {
                b: {
                  advanceTimers(currentTime);
                  for (currentTask = peek(taskQueue); null !== currentTask && !(currentTask.expirationTime > currentTime && shouldYieldToHost()); ) {
                    var callback = currentTask.callback;
                    if ("function" === typeof callback) {
                      currentTask.callback = null;
                      currentPriorityLevel = currentTask.priorityLevel;
                      var continuationCallback = callback(
                        currentTask.expirationTime <= currentTime
                      );
                      currentTime = exports.unstable_now();
                      if ("function" === typeof continuationCallback) {
                        currentTask.callback = continuationCallback;
                        advanceTimers(currentTime);
                        hasMoreWork = true;
                        break b;
                      }
                      currentTask === peek(taskQueue) && pop(taskQueue);
                      advanceTimers(currentTime);
                    } else pop(taskQueue);
                    currentTask = peek(taskQueue);
                  }
                  if (null !== currentTask) hasMoreWork = true;
                  else {
                    var firstTimer = peek(timerQueue);
                    null !== firstTimer && requestHostTimeout(
                      handleTimeout,
                      firstTimer.startTime - currentTime
                    );
                    hasMoreWork = false;
                  }
                }
                break a;
              } finally {
                currentTask = null, currentPriorityLevel = previousPriorityLevel, isPerformingWork = false;
              }
              hasMoreWork = void 0;
            }
          } finally {
            hasMoreWork ? schedulePerformWorkUntilDeadline() : isMessageLoopRunning = false;
          }
        }
      }
      function push(heap, node) {
        var index = heap.length;
        heap.push(node);
        a: for (; 0 < index; ) {
          var parentIndex = index - 1 >>> 1, parent = heap[parentIndex];
          if (0 < compare(parent, node))
            heap[parentIndex] = node, heap[index] = parent, index = parentIndex;
          else break a;
        }
      }
      function peek(heap) {
        return 0 === heap.length ? null : heap[0];
      }
      function pop(heap) {
        if (0 === heap.length) return null;
        var first = heap[0], last = heap.pop();
        if (last !== first) {
          heap[0] = last;
          a: for (var index = 0, length = heap.length, halfLength = length >>> 1; index < halfLength; ) {
            var leftIndex = 2 * (index + 1) - 1, left = heap[leftIndex], rightIndex = leftIndex + 1, right = heap[rightIndex];
            if (0 > compare(left, last))
              rightIndex < length && 0 > compare(right, left) ? (heap[index] = right, heap[rightIndex] = last, index = rightIndex) : (heap[index] = left, heap[leftIndex] = last, index = leftIndex);
            else if (rightIndex < length && 0 > compare(right, last))
              heap[index] = right, heap[rightIndex] = last, index = rightIndex;
            else break a;
          }
        }
        return first;
      }
      function compare(a, b) {
        var diff = a.sortIndex - b.sortIndex;
        return 0 !== diff ? diff : a.id - b.id;
      }
      function advanceTimers(currentTime) {
        for (var timer = peek(timerQueue); null !== timer; ) {
          if (null === timer.callback) pop(timerQueue);
          else if (timer.startTime <= currentTime)
            pop(timerQueue), timer.sortIndex = timer.expirationTime, push(taskQueue, timer);
          else break;
          timer = peek(timerQueue);
        }
      }
      function handleTimeout(currentTime) {
        isHostTimeoutScheduled = false;
        advanceTimers(currentTime);
        if (!isHostCallbackScheduled)
          if (null !== peek(taskQueue))
            isHostCallbackScheduled = true, isMessageLoopRunning || (isMessageLoopRunning = true, schedulePerformWorkUntilDeadline());
          else {
            var firstTimer = peek(timerQueue);
            null !== firstTimer && requestHostTimeout(
              handleTimeout,
              firstTimer.startTime - currentTime
            );
          }
      }
      function shouldYieldToHost() {
        return needsPaint ? true : exports.unstable_now() - startTime < frameInterval ? false : true;
      }
      function requestHostTimeout(callback, ms) {
        taskTimeoutID = localSetTimeout(function() {
          callback(exports.unstable_now());
        }, ms);
      }
      "undefined" !== typeof __REACT_DEVTOOLS_GLOBAL_HOOK__ && "function" === typeof __REACT_DEVTOOLS_GLOBAL_HOOK__.registerInternalModuleStart && __REACT_DEVTOOLS_GLOBAL_HOOK__.registerInternalModuleStart(Error());
      exports.unstable_now = void 0;
      if ("object" === typeof performance && "function" === typeof performance.now) {
        var localPerformance = performance;
        exports.unstable_now = function() {
          return localPerformance.now();
        };
      } else {
        var localDate = Date, initialTime = localDate.now();
        exports.unstable_now = function() {
          return localDate.now() - initialTime;
        };
      }
      var taskQueue = [], timerQueue = [], taskIdCounter = 1, currentTask = null, currentPriorityLevel = 3, isPerformingWork = false, isHostCallbackScheduled = false, isHostTimeoutScheduled = false, needsPaint = false, localSetTimeout = "function" === typeof setTimeout ? setTimeout : null, localClearTimeout = "function" === typeof clearTimeout ? clearTimeout : null, localSetImmediate = "undefined" !== typeof setImmediate ? setImmediate : null, isMessageLoopRunning = false, taskTimeoutID = -1, frameInterval = 5, startTime = -1;
      if ("function" === typeof localSetImmediate)
        var schedulePerformWorkUntilDeadline = function() {
          localSetImmediate(performWorkUntilDeadline);
        };
      else if ("undefined" !== typeof MessageChannel) {
        var channel = new MessageChannel(), port = channel.port2;
        channel.port1.onmessage = performWorkUntilDeadline;
        schedulePerformWorkUntilDeadline = function() {
          port.postMessage(null);
        };
      } else
        schedulePerformWorkUntilDeadline = function() {
          localSetTimeout(performWorkUntilDeadline, 0);
        };
      exports.unstable_IdlePriority = 5;
      exports.unstable_ImmediatePriority = 1;
      exports.unstable_LowPriority = 4;
      exports.unstable_NormalPriority = 3;
      exports.unstable_Profiling = null;
      exports.unstable_UserBlockingPriority = 2;
      exports.unstable_cancelCallback = function(task) {
        task.callback = null;
      };
      exports.unstable_forceFrameRate = function(fps) {
        0 > fps || 125 < fps ? console.error(
          "forceFrameRate takes a positive int between 0 and 125, forcing frame rates higher than 125 fps is not supported"
        ) : frameInterval = 0 < fps ? Math.floor(1e3 / fps) : 5;
      };
      exports.unstable_getCurrentPriorityLevel = function() {
        return currentPriorityLevel;
      };
      exports.unstable_next = function(eventHandler) {
        switch (currentPriorityLevel) {
          case 1:
          case 2:
          case 3:
            var priorityLevel = 3;
            break;
          default:
            priorityLevel = currentPriorityLevel;
        }
        var previousPriorityLevel = currentPriorityLevel;
        currentPriorityLevel = priorityLevel;
        try {
          return eventHandler();
        } finally {
          currentPriorityLevel = previousPriorityLevel;
        }
      };
      exports.unstable_requestPaint = function() {
        needsPaint = true;
      };
      exports.unstable_runWithPriority = function(priorityLevel, eventHandler) {
        switch (priorityLevel) {
          case 1:
          case 2:
          case 3:
          case 4:
          case 5:
            break;
          default:
            priorityLevel = 3;
        }
        var previousPriorityLevel = currentPriorityLevel;
        currentPriorityLevel = priorityLevel;
        try {
          return eventHandler();
        } finally {
          currentPriorityLevel = previousPriorityLevel;
        }
      };
      exports.unstable_scheduleCallback = function(priorityLevel, callback, options) {
        var currentTime = exports.unstable_now();
        "object" === typeof options && null !== options ? (options = options.delay, options = "number" === typeof options && 0 < options ? currentTime + options : currentTime) : options = currentTime;
        switch (priorityLevel) {
          case 1:
            var timeout = -1;
            break;
          case 2:
            timeout = 250;
            break;
          case 5:
            timeout = 1073741823;
            break;
          case 4:
            timeout = 1e4;
            break;
          default:
            timeout = 5e3;
        }
        timeout = options + timeout;
        priorityLevel = {
          id: taskIdCounter++,
          callback,
          priorityLevel,
          startTime: options,
          expirationTime: timeout,
          sortIndex: -1
        };
        options > currentTime ? (priorityLevel.sortIndex = options, push(timerQueue, priorityLevel), null === peek(taskQueue) && priorityLevel === peek(timerQueue) && (isHostTimeoutScheduled ? (localClearTimeout(taskTimeoutID), taskTimeoutID = -1) : isHostTimeoutScheduled = true, requestHostTimeout(handleTimeout, options - currentTime))) : (priorityLevel.sortIndex = timeout, push(taskQueue, priorityLevel), isHostCallbackScheduled || isPerformingWork || (isHostCallbackScheduled = true, isMessageLoopRunning || (isMessageLoopRunning = true, schedulePerformWorkUntilDeadline())));
        return priorityLevel;
      };
      exports.unstable_shouldYield = shouldYieldToHost;
      exports.unstable_wrapCallback = function(callback) {
        var parentPriorityLevel = currentPriorityLevel;
        return function() {
          var previousPriorityLevel = currentPriorityLevel;
          currentPriorityLevel = parentPriorityLevel;
          try {
            return callback.apply(this, arguments);
          } finally {
            currentPriorityLevel = previousPriorityLevel;
          }
        };
      };
      "undefined" !== typeof __REACT_DEVTOOLS_GLOBAL_HOOK__ && "function" === typeof __REACT_DEVTOOLS_GLOBAL_HOOK__.registerInternalModuleStop && __REACT_DEVTOOLS_GLOBAL_HOOK__.registerInternalModuleStop(Error());
    })();
  }
});

// node_modules/scheduler/index.js
var require_scheduler = __commonJS({
  "node_modules/scheduler/index.js"(exports, module) {
    "use strict";
    if (false) {
      module.exports = null;
    } else {
      module.exports = require_scheduler_development();
    }
  }
});

// lib/mustang/parts.ts
function define(list) {
  const out = {};
  for (const item of list) {
    out[item.id] = {
      id: item.id,
      name: item.name,
      system: item.system,
      stage: item.stage,
      ex: item.ex ?? [0, 0, 0],
      parent: item.parent,
      circuit: item.circuit,
      blurb: item.blurb,
      specs: item.specs ?? [],
      fasteners: item.fasteners ?? [],
      checks: item.checks,
      keywords: item.keywords ?? [],
      alt: item.alt
    };
  }
  return out;
}
var lug = {
  name: "Lug nut",
  thread: '1/2"-20 UNF',
  torque: "95 lb-ft \xB7 60\xB0 cone",
  qty: "5"
};
var wheelSpecs = [
  { label: "Tire", value: "P205/65R15 (base)" },
  { label: "Pattern", value: "5\xD74.5 in (5\xD7114.3 mm)" },
  { label: "Stud", value: '1/2"-20' }
];
function wheel(id, name, ex, place) {
  return {
    id,
    name,
    system: "suspension",
    stage: 2,
    ex,
    blurb: `${place}. Base coupe wears a 15-inch steel wheel and a cover, not a GT alloy. Tire is P205/65R15 unless someone has already swapped it.`,
    specs: wheelSpecs,
    fasteners: [lug, { name: "Stud", thread: '1/2"-20', qty: "5" }],
    checks: [
      "Torque in a star, then again after about 50 miles. Aftermarket nuts often have the wrong seat.",
      "Cold pressure is the door-jamb sticker, not the sidewall maximum.",
      "A chop in the tread is a dead strut or a weight that left. Inner-shoulder wear is alignment, not 'it needs air'."
    ],
    keywords: ["tire", "lug", "stud", "wheel", "balance"]
  };
}
var PLUG = [
  { label: "Motorcraft", value: "AWSF-42EE (match the VECI suffix)" },
  { label: "Gap", value: "1.3\u20131.4 mm (0.052\u20130.056 in)" },
  { label: "Thread", value: "14 mm \xD7 1.25" },
  { label: "Seat", value: "Gasket, iron head" }
];
function plugs(id, name, parent, ex, bank) {
  return {
    id,
    name,
    system: "engine",
    stage: 5,
    parent,
    ex,
    circuit: "ignition",
    blurb: `${bank}. Waste-spark EDIS, so a coil tower feeds two cylinders. If you only inspect a plug, it goes back in the same hole. Replacement plugs must use the suffix letter on the VECI decal.`,
    specs: PLUG,
    fasteners: [
      {
        name: "Spark plug",
        thread: "14 mm \xD7 1.25",
        torque: "Snug on the iron head, about 7\u201315 lb-ft. Do not reef it.",
        qty: "3 this bank"
      }
    ],
    checks: [
      "Oil-soaked boots mean the valve cover is leaking onto the wire. The miss will come back if you only change the plug.",
      "Carbon tracking up the porcelain is a bad wire or a loose boot, not a carburetor problem. This car never had a carb.",
      "Anti-seize is optional on an iron head and changes torque. If you use it, use less torque, not more."
    ],
    keywords: ["spark", "plug", "misfire", "gap", "awsf"]
  };
}
var PARTS = define([
  {
    id: "unibody",
    name: "Unibody shell",
    system: "chassis",
    stage: 0,
    blurb: "The painted shell stays put so you can see what left it. Panels, glass, and the powertrain move off this shape. It is a New Edge coupe: long hood, short deck, tri-bar tails.",
    specs: [
      { label: "Body", value: "2-door coupe" },
      { label: "Wheelbase", value: "101.3 in" },
      { label: "Length", value: "183.2 in" }
    ],
    checks: [
      "Panel gaps tell you if the car was hit. Compare hood-to-fender and door-to-quarter before you buy parts.",
      "This shell is the reference. If a part highlight doesn't sit where it does on your car, trust the car \u2014 aftermarket panels move the gaps."
    ],
    keywords: ["unibody", "body", "shell", "coupe"]
  },
  {
    id: "floor",
    name: "Floor pan",
    system: "chassis",
    stage: 0,
    blurb: "The unibody floor stays put so the rest of the car has a home. Torque boxes and the seat-pan welds live here.",
    checks: [
      "Soft floors under the carpet are usually the footwells or the spare-tire well, not a dramatic frame rail.",
      "A cracked torque box (where the control arm meets the floor) knocks and walks the alignment. Look there before you buy struts."
    ],
    keywords: ["floor", "unibody", "rust", "torque box"]
  },
  {
    id: "firewall",
    name: "Firewall",
    system: "chassis",
    stage: 0,
    blurb: "Cowl and firewall. The PCM harness, heater core, and brake booster all pass through this wall.",
    checks: [
      "A wet passenger floor with a sweet smell is the heater core or the heater hose at the firewall, not a windshield leak \u2014 until you prove it.",
      "Harness grommets that are pulled out chew wires. Look here when a circuit only fails over bumps."
    ],
    keywords: ["firewall", "cowl", "grommet"]
  },
  {
    id: "tunnel",
    name: "Transmission tunnel",
    system: "chassis",
    stage: 0,
    blurb: "The driveshaft and shifter live under this hump. Heat here is normal. Smoke is not.",
    checks: [
      "A hot tunnel and a burning smell after a long pull is often a driveshaft hitting the tunnel, or a parking-brake cable on the exhaust.",
      "Shifter boots tear and dump water into the trans. The boot is a part, not trim."
    ],
    keywords: ["tunnel", "shifter"]
  },
  {
    id: "tower-l",
    name: "Driver strut tower",
    system: "chassis",
    stage: 0,
    blurb: "MacPherson tower, driver side. The strut nut and the camber plate, if anyone added one, live on top.",
    checks: [
      "Torn tower sheet metal around the studs is a common SN95 crack. A clunk that is not the end link is sometimes the tower.",
      "Do not loosen the top nut without the spring compressed. The spring is still loaded with the car in the air if the arm is hanging."
    ],
    keywords: ["strut tower", "camber"]
  },
  {
    id: "tower-r",
    name: "Passenger strut tower",
    system: "chassis",
    stage: 0,
    blurb: "Passenger MacPherson tower. Battery and the power box sit just ahead of it.",
    checks: [
      "Same crack check as the driver side. The battery tray also hides rust where it bolts to the apron.",
      "A loose battery hold-down lets the case beat this tower apart. Hold it down."
    ],
    keywords: ["strut tower"]
  },
  {
    id: "core-support",
    name: "Radiator support",
    system: "chassis",
    stage: 0,
    blurb: "Upper and lower core support. The radiator, hood latch, and the belt-routing sticker live here.",
    checks: [
      "A light hit folds this before it folds the rails. Gaps at the hood and headlights tell you first.",
      "The belt sticker on this panel is the routing that matches the car. Phone photos of other years are how belts get inside-out."
    ],
    keywords: ["core support", "radiator support", "latch"]
  },
  {
    id: "rocker-l",
    name: "Driver rocker",
    system: "body",
    stage: 1,
    ex: [-0.22, 0, 0],
    blurb: "Driver sill. The fuel-pump harness and the parking-brake cable run this side of the car.",
    checks: [
      "Jack only on the pinch weld or a rail, with a block. A puck through the rocker skin is a permanent dent.",
      "Rust here is structural. A bubbling rocker is not a bondo job if the jack point is gone."
    ],
    keywords: ["rocker", "sill", "jack"]
  },
  {
    id: "rocker-r",
    name: "Passenger rocker",
    system: "body",
    stage: 1,
    ex: [0.22, 0, 0],
    blurb: "Passenger sill. Mirror of the driver side, without the fuel-pump run.",
    checks: [
      "Same jack rule. Don't lift on the seam with a bare saddle.",
      "Compare both rockers. A car that sits low on one side is often a spring, not a bent sill."
    ],
    keywords: ["rocker", "sill"]
  },
  {
    id: "hood",
    name: "Hood",
    system: "body",
    stage: 1,
    ex: [0, 0.78, -0.45],
    blurb: "Base hood. No Cobra scoop. A prop rod holds it, not struts. Latch and the safety catch both have to click.",
    specs: [{ label: "Hold", value: "Prop rod, driver side of the bay" }],
    fasteners: [
      { name: "Hinge bolt", thread: "Metric, confirm before you order", qty: "2 per hinge" }
    ],
    checks: [
      "Gaps are hinges plus the rubber bumpers. Don't slot the latch until the hinges are even.",
      "The safety catch is what saves you at 70 if the latch cable sticks. Make it work.",
      "Prop the rod in its clip. A hood on the back of your head is a bad afternoon."
    ],
    keywords: ["hood", "latch", "prop"]
  },
  {
    id: "fender-fl",
    name: "Driver front fender",
    system: "body",
    stage: 1,
    ex: [-0.42, 0.12, -0.08],
    blurb: "Bolt-on fender over the driver front wheel. The side marker and the apron bolts are the usual fight.",
    checks: [
      "Lined up to the hood and the door, not to the bumper cover alone. Bumper covers move.",
      "Captured nuts in the apron strip. A spinning nut means the apron, not 'just a bigger screwdriver'."
    ],
    keywords: ["fender"]
  },
  {
    id: "fender-fr",
    name: "Passenger front fender",
    system: "body",
    stage: 1,
    ex: [0.42, 0.12, -0.08],
    blurb: "Passenger bolt-on fender. Battery tray and the power box sit inboard of it.",
    checks: [
      "Same gap rules as the driver side.",
      "If the headlight bucket is cracked, the fender will never gap. Fix the bucket first."
    ],
    keywords: ["fender"]
  },
  {
    id: "door-l",
    name: "Driver door",
    system: "body",
    stage: 1,
    ex: [-0.72, 0.04, 0],
    blurb: "Driver door. These sag. It is almost always the hinge pins and bushings, not a bent shell.",
    checks: [
      "Lift the door by the handle while a second person watches the hinge. Movement there is pins.",
      "Support the door before the hinge bolts come out. The shell will fold over your knee.",
      "A door that pops over bumps needs the striker moved, after the pins are good. Striker first is how you bend the latch."
    ],
    keywords: ["door", "hinge", "sag", "striker", "window"]
  },
  {
    id: "door-r",
    name: "Passenger door",
    system: "body",
    stage: 1,
    ex: [0.72, 0.04, 0],
    blurb: "Passenger door. Same hinge-pin failure as the driver side, plus the latch you use less often, which sticks.",
    checks: [
      "Work the latch with the door open. A lazy pawl is the latch, not the handle.",
      "Window regulators fail on both doors. A glass that cocks is the regulator, not the switch, until you prove power at the motor."
    ],
    keywords: ["door", "hinge", "regulator"]
  },
  {
    id: "glass-door-l",
    name: "Driver door glass",
    system: "glass",
    stage: 2,
    parent: "door-l",
    ex: [-0.16, 0.12, 0],
    blurb: "Door glass on the driver side. It rides a regulator and two channels.",
    checks: [
      "If it drops into the door, do not cycle the switch. The glass will wedge and the regulator will strip.",
      "Channels dry out and slow the glass before the motor dies. Silicone on the channel, not oil on the felt."
    ],
    keywords: ["window", "glass", "regulator"]
  },
  {
    id: "glass-door-r",
    name: "Passenger door glass",
    system: "glass",
    stage: 2,
    parent: "door-r",
    ex: [0.16, 0.12, 0],
    blurb: "Passenger door glass. Same regulator layout as the driver door.",
    checks: [
      "Listen at the motor with the panel off. A motor that hums and doesn't move is the regulator. A silent motor is power or the switch.",
      "Don't mix the clips. They are side-specific enough to ruin a afternoon."
    ],
    keywords: ["window", "glass"]
  },
  {
    id: "quarter-l",
    name: "Driver quarter",
    system: "body",
    stage: 1,
    ex: [-0.38, 0.1, 0.18],
    blurb: "Driver quarter panel. The fuel door and the New Edge scoop sit on this skin. The inner wheelhouse is where these cars rot.",
    checks: [
      "Pull the trunk side carpet. Rust starts at the wheelhouse lip and the drop-off, not in the middle of the paint.",
      "A quarter is welded. A 'bolt-on' quote is a clip job. Ask where they cut."
    ],
    keywords: ["quarter", "rust", "wheelhouse"]
  },
  {
    id: "quarter-r",
    name: "Passenger quarter",
    system: "body",
    stage: 1,
    ex: [0.38, 0.1, 0.18],
    blurb: "Passenger quarter. Same wheelhouse rust pattern, no fuel door.",
    checks: [
      "Compare the trunk gutters side to side after a wash. Water that stays on one side is a drain or a seam.",
      "Tail-lamp studs strip the plastic housing and then the quarter looks crooked. It's often the lamp, not the panel."
    ],
    keywords: ["quarter"]
  },
  {
    id: "scoop-l",
    name: "Driver side scoop",
    system: "body",
    stage: 1,
    parent: "quarter-l",
    ex: [-0.14, 0, 0],
    blurb: "The New Edge scoop behind the driver door. On a base car it is a styling opening, not a cold-air feed.",
    checks: [
      "They crack at the mounting tabs. A scoop that rattles is loose screws or a broken tab, not the quarter.",
      "Don't caulk it shut. Water is supposed to drain, not fill the cavity."
    ],
    keywords: ["scoop"]
  },
  {
    id: "scoop-r",
    name: "Passenger side scoop",
    system: "body",
    stage: 1,
    parent: "quarter-r",
    ex: [0.14, 0, 0],
    blurb: "Passenger scoop. Same part, other side.",
    checks: ["Same tab and rattle check as the driver scoop."],
    keywords: ["scoop"]
  },
  {
    id: "roof",
    name: "Roof",
    system: "body",
    stage: 1,
    ex: [0, 0.62, 0],
    blurb: "Coupe roof and pillars. This is a fixed roof, not a convertible top. The headliner bows when the bows or the adhesive let go.",
    checks: [
      "A dripping headliner is usually the windshield or the roof seam at the A-pillar, not the sunroof you don't have.",
      "Pillar trim clips break. Order clips before you pull the trim or the airbag cover becomes a project."
    ],
    keywords: ["roof", "headliner", "pillar"]
  },
  {
    id: "windshield",
    name: "Windshield",
    system: "glass",
    stage: 1,
    ex: [0, 0.4, -0.32],
    blurb: "Bonded windshield. It is part of the cowl stiffness. A bad urethane job whistles and leaks down the A-pillar into the fuse area.",
    checks: [
      "Leaks show at the top corners first. Hose-test before you replace a heater core for a wet floor.",
      "VIN plate is at the base. Don't sand it off during a chip repair."
    ],
    keywords: ["windshield", "glass", "leak"]
  },
  {
    id: "rear-glass",
    name: "Backlight",
    system: "glass",
    stage: 1,
    ex: [0, 0.42, 0.28],
    blurb: "Coupe rear glass, bonded, with the defroster grid baked in.",
    checks: [
      "A dead defroster with one line open can be repaired. A dead grid with no power is the switch or the timer, not the glass.",
      "The pigtail at the glass breaks when someone yanks the parcel shelf. Look there first."
    ],
    keywords: ["rear window", "defroster", "backlight"]
  },
  {
    id: "trunk",
    name: "Deck lid",
    system: "body",
    stage: 1,
    ex: [0, 0.52, 0.5],
    blurb: "Trunk lid. Torsion rods, not struts, do the lifting. They are loaded.",
    checks: [
      "Do not pry a torsion rod off without a hand and a plan. They leave the car.",
      "Weatherstrip that is crushed at the bottom fills the spare well. The well then looks like a quarter leak.",
      "Latch adjustment is the striker. The key cylinder is a separate, tired part."
    ],
    keywords: ["trunk", "decklid", "torsion"]
  },
  {
    id: "fuel-door",
    name: "Fuel door",
    system: "body",
    stage: 1,
    parent: "quarter-l",
    ex: [-0.1, 0, 0],
    blurb: "Fuel filler door on the driver quarter. The cap is a sealed cap on a returnless system. A loose cap sets an evap code.",
    specs: [{ label: "Tank", value: "15.7 gal" }],
    checks: [
      "Tighten until it clicks. A 'good enough' cap is a check-engine light.",
      "The door hinge breaks. The neck behind it is plastic and cracks if you lever the door."
    ],
    keywords: ["fuel door", "gas cap", "evap"]
  },
  {
    id: "bumper-f",
    name: "Front bumper cover",
    system: "body",
    stage: 1,
    ex: [0, 0.02, -0.5],
    blurb: "Body-color front cover with a black lower valence. It is plastic on a steel impact bar. The cover moves; the bar is the structure.",
    checks: [
      "A cover that fits at the top and sticks out at the bottom usually means a bent impact bar or a broken retainer, not 'it needs heat'.",
      "Fog lamps were not standard on the base car. A hole there with no lamp is a broken cover or a GT cover someone hung on it."
    ],
    keywords: ["bumper", "fascia", "valence"]
  },
  {
    id: "bumper-r",
    name: "Rear bumper cover",
    system: "body",
    stage: 1,
    ex: [0, 0.04, 0.48],
    blurb: "Rear cover. The base car has a single exhaust tip on the passenger side, not the GT's two.",
    checks: [
      "Exhaust clearance is the tip versus this cover. A rattle back here is often the tip touching, or a loose energy absorber.",
      "Park-sensor holes don't belong on a 2001 base. If you see them, the cover is from something else."
    ],
    keywords: ["bumper", "rear"]
  },
  {
    id: "grille",
    name: "Grille",
    system: "body",
    stage: 1,
    ex: [0, 0.04, -0.32],
    blurb: "Front grille opening in the bumper cover. The pony is an emblem, not a structural part. The opening is how the radiator breathes.",
    checks: [
      "Leaves pack the A/C condenser first, then the radiator. Rinse from the engine side out so you don't fold the fins into a wall.",
      "A missing emblem is cosmetic. A blocked opening is why it overheats in traffic and not on the highway."
    ],
    keywords: ["grille", "emblem"]
  },
  {
    id: "headlamp-l",
    name: "Driver headlamp",
    system: "electrical",
    stage: 1,
    ex: [-0.16, 0.1, -0.34],
    circuit: "lamps",
    blurb: "Composite headlamp, driver side. A clear lens in front of a replaceable bulb. The bucket is adjusted with two screws, not by bending the fender.",
    specs: [
      { label: "Low / high", value: "9007-style dual filament on many of these; confirm the bulb in the housing" }
    ],
    checks: [
      "Moisture that keeps returning is a cracked housing or a bad vent, not 'the bulb is hot'.",
      "Aim after any fender or bucket work. A lamp pointed at the weeds is why oncoming traffic flashes you.",
      "Ground for this lamp is in the front harness. A dim side with a good bulb is usually the ground, not the switch."
    ],
    keywords: ["headlight", "headlamp", "bulb", "aim"]
  },
  {
    id: "headlamp-r",
    name: "Passenger headlamp",
    system: "electrical",
    stage: 1,
    ex: [0.16, 0.1, -0.34],
    circuit: "lamps",
    blurb: "Passenger composite headlamp. Same service rules as the driver side.",
    checks: [
      "Swap the bulb left to right before you buy a switch. Bulbs are cheaper than diagnosis, and they fail one at a time.",
      "The connector gets green. A little contact cleaner and a tight pin beat a new harness."
    ],
    keywords: ["headlight", "headlamp"]
  },
  {
    id: "taillamp-l",
    name: "Driver tail lamp",
    system: "electrical",
    stage: 1,
    ex: [-0.12, 0.08, 0.3],
    circuit: "lamps",
    blurb: "Driver tri-bar tail lamp. Three vertical bars. That is the New Edge signature, and the brake, tail, and turn sections are in this housing.",
    checks: [
      "A fast blinker is a bulb or a ground in this housing, not the flasher module, until both sides are fast.",
      "Sockets melt. Look at the plastic before you keep feeding it bulbs.",
      "The housing seals to the quarter. A wet trunk corner is often this gasket."
    ],
    keywords: ["tail", "brake light", "turn", "tri-bar"]
  },
  {
    id: "taillamp-r",
    name: "Passenger tail lamp",
    system: "electrical",
    stage: 1,
    ex: [0.12, 0.08, 0.3],
    circuit: "lamps",
    blurb: "Passenger tri-bar. Same bulb layout. The reverse lamp is in the housing too.",
    checks: [
      "Reverse only works in reverse, with the switch on the trans. A dead reverse lamp and a good bulb is that switch more often than the housing.",
      "Same socket-melt and gasket checks as the driver side."
    ],
    keywords: ["tail", "reverse"]
  },
  {
    id: "mirror-l",
    name: "Driver mirror",
    system: "body",
    stage: 1,
    parent: "door-l",
    ex: [-0.18, 0.08, 0],
    blurb: "Driver outside mirror. Base cars are often manual, some are power. The glass is a replaceable pane.",
    checks: [
      "A power mirror that is dead on one axis is the motor in the head. Dead on both axes is the switch or the 12 V feed in the door boot.",
      "The boot between door and body is where the wires break. Flex it while you watch the glass."
    ],
    keywords: ["mirror"]
  },
  {
    id: "mirror-r",
    name: "Passenger mirror",
    system: "body",
    stage: 1,
    parent: "door-r",
    ex: [0.18, 0.08, 0],
    blurb: "Passenger mirror. Same idea, longer wires through the passenger door boot.",
    checks: ["Flex the door boot if the glass quits only with the door open or shut."],
    keywords: ["mirror"]
  },
  wheel("wheel-fl", "Driver front wheel", [-0.62, 0, 0], "Driver front"),
  wheel("wheel-fr", "Passenger front wheel", [0.62, 0, 0], "Passenger front"),
  wheel("wheel-rl", "Driver rear wheel", [-0.62, 0, 0], "Driver rear"),
  wheel("wheel-rr", "Passenger rear wheel", [0.62, 0, 0], "Passenger rear"),
  {
    id: "rotor-fl",
    name: "Driver front rotor",
    system: "brake",
    stage: 3,
    ex: [-0.24, 0, 0],
    blurb: "Front disc, driver side. Base cars are disc/drum. Measure thickness and runout before you turn a rotor that is already at the lip.",
    specs: [{ label: "Layout", value: "Front disc, rear drum on the base car" }],
    checks: [
      "A pedal that pulses under light braking is thickness variation. Runout measured on the hub, not guessed from the pad.",
      "Hub rust under the rotor cocks it. Wire-brush the face. A new rotor on a rusty hub pulses immediately.",
      "Don't grease the friction surface. A little anti-seize on the hat where it meets the hub is enough, and keep it off the studs' cone."
    ],
    keywords: ["rotor", "disc", "brake", "pulsation"]
  },
  {
    id: "rotor-fr",
    name: "Passenger front rotor",
    system: "brake",
    stage: 3,
    ex: [0.24, 0, 0],
    blurb: "Passenger front rotor. Same measurement rules.",
    checks: [
      "Replace or machine in pairs. One new rotor and one old one pulls.",
      "Check the hose. A collapsed hose makes one side drag and cooks this rotor."
    ],
    keywords: ["rotor", "brake"]
  },
  {
    id: "caliper-fl",
    name: "Driver front caliper",
    system: "brake",
    stage: 3,
    ex: [-0.32, 0.14, 0],
    blurb: "Single-piston sliding caliper. The slide pins do the work. The bracket bolts are not the slide pins \u2014 don't mix up the torque.",
    specs: [{ label: "Fluid", value: "Motorcraft High Performance DOT 3, fill to the reservoir line" }],
    fasteners: [
      { name: "Slide pin", thread: "Small, boot-sealed", torque: "Low. Confirm in the shop manual. Grease the pin, not the pad face." },
      { name: "Bracket bolt", thread: "Larger than the pin", torque: "High. Do not treat it like a slide pin." }
    ],
    checks: [
      "Torn pin boots wet the grease and the caliper sticks. That's the pull and the smell.",
      "Bleeder on top. If the bleeder is on the bottom, the caliper is on the wrong side.",
      "Don't push a piston back on a car that might have ABS without cracking the bleeder. You shove dirt at the valves. This base car may not have ABS \u2014 look for the module before you assume."
    ],
    keywords: ["caliper", "pad", "slide pin", "dot 3"]
  },
  {
    id: "caliper-fr",
    name: "Passenger front caliper",
    system: "brake",
    stage: 3,
    ex: [0.32, 0.14, 0],
    blurb: "Passenger front caliper. Bleeder up. Opposite of the driver caliper, so they are not interchangeable.",
    checks: [
      "Same pin and hose checks.",
      "A soft hose looks fine and still acts like a check valve. If this side drags after a drive, crack the bleeder. If the wheel frees instantly, the hose or the master is holding pressure."
    ],
    keywords: ["caliper"]
  },
  {
    id: "drum-rl",
    name: "Driver rear drum",
    system: "brake",
    stage: 3,
    ex: [-0.28, 0, 0],
    blurb: "Rear drum, driver side. Base V6 did not get the GT's rear discs. The self-adjuster and the parking-brake cable live in here.",
    checks: [
      "A low pedal that pumps up is often the rears out of adjustment, or a leaking wheel cylinder.",
      "Wheel cylinder: peel the boot. Brake fluid behind it means replace the cylinder and bleed, not 'wipe and hope'.",
      "Adjuster threads seize. The shoe never grows. Clean and a dry lube on the threads, then adjust through the slot.",
      "Parking-brake cables freeze. A drum that drags after a rain sat with the cable applied."
    ],
    keywords: ["drum", "shoe", "parking brake", "wheel cylinder"]
  },
  {
    id: "drum-rr",
    name: "Passenger rear drum",
    system: "brake",
    stage: 3,
    ex: [0.28, 0, 0],
    blurb: "Passenger rear drum. Same hardware, and the cable run is the long one.",
    checks: [
      "Do both sides. One fresh cylinder and one old one gives you a pull and a comeback.",
      "Spring pliers or a good pair of dikes as a last resort. Flying springs find eyes."
    ],
    keywords: ["drum", "shoe"]
  },
  {
    id: "strut-fl",
    name: "Driver front strut",
    system: "suspension",
    stage: 3,
    ex: [-0.22, 0.2, 0],
    blurb: "MacPherson strut, driver front. The spring is captive. A dead strut lets the tire cup and the car float.",
    checks: [
      "Bounce the corner. More than one extra swing is done. Oil on the tube confirms it.",
      "The top mount bearing clunks when you turn the wheel at a stop. Don't buy a strut for a bearing.",
      "Compress the spring in a real compressor. Fence wire is how struts leave the bay."
    ],
    keywords: ["strut", "spring", "clunk"]
  },
  {
    id: "strut-fr",
    name: "Passenger front strut",
    system: "suspension",
    stage: 3,
    ex: [0.22, 0.2, 0],
    blurb: "Passenger front strut. Replace in pairs if the car has miles on both.",
    checks: ["Same bounce and mount checks. A car that sits low in front is springs, not struts. Struts don't hold the car up."],
    keywords: ["strut"]
  },
  {
    id: "lca-fl",
    name: "Driver lower control arm",
    system: "suspension",
    stage: 3,
    ex: [0, -0.24, -0.05],
    blurb: "Driver front lower control arm and ball joint. The ball joint is the pivot the tire steers on.",
    checks: [
      "Jack so the arm hangs. Pry at the joint. Play you can see is the joint. Play you imagine is the bushing.",
      "A torn rear bushing walks under braking. The car darts. That's this arm, not the rack, until the rack actually leaks."
    ],
    keywords: ["control arm", "ball joint", "bushing"]
  },
  {
    id: "lca-fr",
    name: "Passenger lower control arm",
    system: "suspension",
    stage: 3,
    ex: [0, -0.24, -0.05],
    blurb: "Passenger lower control arm. Same checks, other side.",
    checks: ["Do the pry test with the wheel straight. A joint that only shows play while turned can still be done \u2014 compare sides."],
    keywords: ["control arm", "ball joint"]
  },
  {
    id: "swaybar",
    name: "Front sway bar",
    system: "suspension",
    stage: 3,
    ex: [0, -0.2, -0.2],
    blurb: "Front anti-roll bar and end links. The cheapest clunk on the car, and the one people replace struts to fix.",
    checks: [
      "Grab the end link. Any knock is the link or the bar bushing. The bar itself rarely bends unless the car was curbed.",
      "Bushings are split. Mark the bar's position in the bushing or the car will sit twisted."
    ],
    keywords: ["sway bar", "end link", "clunk"]
  },
  {
    id: "rack",
    name: "Steering rack",
    system: "suspension",
    stage: 3,
    ex: [0, -0.18, -0.28],
    blurb: "Power rack and pinion. The 3.8 pump uses MERCON ATF, not a random power-steering fluid. Inner ties and the bellows live on the rack.",
    specs: [
      { label: "Fluid", value: "Motorcraft MERCON ATF (3.8 pump). Keep the dipstick in the FULL HOT range." }
    ],
    checks: [
      "Wet bellows are an inner seal or an outer tie-rod boot that's been open for years. Cut the bellows only when you're ready to replace the part you find.",
      "A groan in the steering at full lock, with the level full and the belt quiet, is the pump or air in the system. Bleed it before you buy a pump.",
      "Outer tie-rod play shows up as toe that won't hold. Set toe last, after the ties are tight."
    ],
    keywords: ["rack", "power steering", "tie rod", "mercon"]
  },
  {
    id: "spring-rl",
    name: "Driver rear spring",
    system: "suspension",
    stage: 3,
    ex: [-0.2, 0.28, 0],
    blurb: "Coil spring on the driver side of the solid axle. These sag. A Mustang that looks lowered in the back and wasn't, needs springs.",
    checks: [
      "Measure ride height side to side before you condemn a spring. A bent axle pad or a tired bushing mimics sag.",
      "The spring is trapped by the axle. Support the axle and the body. Letting the axle hang on the brake hose ruins the hose."
    ],
    keywords: ["spring", "ride height"]
  },
  {
    id: "spring-rr",
    name: "Passenger rear spring",
    system: "suspension",
    stage: 3,
    ex: [0.2, 0.28, 0],
    blurb: "Passenger rear coil. Matched to the driver side if you replace them.",
    checks: ["Replace as a pair. One new spring and one old one is a lean you will chase forever."],
    keywords: ["spring"]
  },
  {
    id: "shock-rl",
    name: "Driver rear shock",
    system: "suspension",
    stage: 3,
    ex: [-0.18, 0.22, 0.1],
    blurb: "Vertical rear shock, driver side. There are also horizontal quad shocks. This one controls the bounce. The quads control axle wrap.",
    checks: [
      "Oil on the body, or a bounce that doesn't stop, is this shock.",
      "The upper mount in the trunk floor tears out. A banging rear end with a new shock is often the mount."
    ],
    keywords: ["shock"]
  },
  {
    id: "shock-rr",
    name: "Passenger rear shock",
    system: "suspension",
    stage: 3,
    ex: [0.18, 0.22, 0.1],
    blurb: "Passenger vertical rear shock.",
    checks: ["Same mount check inside the trunk. Don't torque the lower bolt with the axle hanging at full droop or the bushing lives twisted."],
    keywords: ["shock"]
  },
  {
    id: "quad-l",
    name: "Driver quad shocks",
    system: "suspension",
    stage: 3,
    ex: [-0.16, -0.08, -0.2],
    blurb: "Horizontal shocks on the driver side, two of them. They stop the axle from wrapping up on a hard launch. A base car still has them.",
    checks: [
      "A clunk when you get on and off the throttle is often a quad bushing, not the rear end.",
      "They are easy to install backwards in spirit: the body and the shaft have a direction. Note which end faces the axle before they come off."
    ],
    keywords: ["quad shock", "wheel hop"]
  },
  {
    id: "quad-r",
    name: "Passenger quad shocks",
    system: "suspension",
    stage: 3,
    ex: [0.16, -0.08, -0.2],
    blurb: "Passenger horizontal quad shocks.",
    checks: ["Same clunk check. A missing quad is why a 3.8 still wheel-hops."],
    keywords: ["quad shock"]
  },
  {
    id: "uca-l",
    name: "Driver upper control arm",
    system: "suspension",
    stage: 3,
    ex: [-0.2, 0.12, -0.12],
    blurb: "Upper arm locating the axle on the driver side. Bushings here set wheel hop and a clunk when you shift.",
    checks: [
      "Pry between the arm and the mount. A bushing that has left the shell is done.",
      "Torque the pivot with the car at ride height. Tightening it on a hanging axle winds the bushing up and it tears in a month."
    ],
    keywords: ["upper control arm", "bushing"]
  },
  {
    id: "uca-r",
    name: "Passenger upper control arm",
    system: "suspension",
    stage: 3,
    ex: [0.2, 0.12, -0.12],
    blurb: "Passenger upper control arm.",
    checks: ["Same ride-height torque rule. Do both arms if one is oil-soaked. The axle will sit crooked if you only do one."],
    keywords: ["upper control arm"]
  },
  {
    id: "axle",
    name: "7.5-inch rear axle",
    system: "driveline",
    stage: 3,
    ex: [0, -0.32, 0.08],
    blurb: "Ford 7.5-inch axle, open differential on a base V6. This is not the GT 8.8. Common gears are about 3.27 with the T-5 and 2.73 with the automatic. The tag or the door sticker wins.",
    specs: [
      { label: "Housing", value: "7.5 in, open, unless someone swapped it" },
      { label: "Fluid", value: "Fill to the bottom of the fill hole. Read the tag before you buy a ratio." },
      { label: "Brakes", value: "Drums on the base car" }
    ],
    fasteners: [
      { name: "Fill plug", thread: "Confirm on the housing", torque: "Snug. Do not round it." }
    ],
    checks: [
      "A howl that changes with speed and stays when you clutch-in is the axle, not the trans. A noise that leaves when you unload the throttle is often the pinion bearing.",
      "Don't crack the cover until you can refill it. These get driven home empty.",
      "The vent on top plugs and then pinion seals push out. Clean the vent before you condemn a seal that just got replaced."
    ],
    keywords: ["axle", "7.5", "differential", "gear", "pinion"]
  },
  {
    id: "driveshaft",
    name: "Driveshaft",
    system: "driveline",
    stage: 3,
    ex: [0, -0.42, 0],
    blurb: "One-piece steel shaft, two U-joints, from the transmission to the pinion.",
    checks: [
      "A clunk when you shift from drive to reverse, or when you let the clutch out, is a U-joint before it is a differential.",
      "Mark the shaft to the pinion flange before it comes apart. A shaft installed 180\xB0 out vibrates at highway speed.",
      "Don't let it hang on the slip yoke. The seal in the trans cuts, and then it leaks at the yoke."
    ],
    keywords: ["driveshaft", "u-joint", "vibration"]
  },
  {
    id: "trans",
    name: "T-5 5-speed",
    system: "driveline",
    stage: 3,
    ex: [0, -0.55, 0.12],
    blurb: "World-class T-5, the standard gearbox on the base car. Fluid in the 2001 manual is MERCON ATF. Fill to the fill plug. Do not overfill it.",
    specs: [
      { label: "Fluid", value: "Motorcraft MERCON ATF (manual spec XT-2-QDX)" },
      { label: "Fill", value: "Bottom of the fill plug. Not 'until it runs down the case forever'." },
      { label: "Clutch", value: "Cable, not hydraulic" }
    ],
    checks: [
      "Second and third synchros go first. A grind only on a fast shift is a synchro. A grind in every gear with the pedal down is the clutch not releasing.",
      "The shifter cup and bushings feel like a bad trans. Wiggle the lever in neutral. A dinner-plate of play is the bushing, a $15 part.",
      "Overfilling pushes fluid out the vent and onto the exhaust. Then the car 'burns trans fluid' that you just poured in."
    ],
    keywords: ["transmission", "t-5", "t5", "manual", "synchro", "mercon"],
    alt: {
      when: "4r70w",
      name: "4R70W automatic",
      blurb: "Optional 4-speed automatic. The 2001 manual calls for MERCON V, not the MERCON used in the T-5. Level is checked warm, engine running, in Park, on level ground.",
      specs: [
        { label: "Fluid", value: "MERCON V (manual spec XT-5-QM)" },
        { label: "Level", value: "Hot, idling, in Park. Read both sides of the stick." }
      ],
      checks: [
        "Do not put MERCON V in a T-5 or plain MERCON in this 4R70W. They are not the same bottle.",
        "A flare between gears with the level correct is clutches or the valve body, not 'add a bottle of mystery stop-slip' as a first move.",
        "The cooler lines at the radiator leak and then the trans burns up three days later. Look at the fittings while it is still a leak."
      ]
    }
  },
  {
    id: "clutch",
    name: "Clutch and cable",
    system: "driveline",
    stage: 4,
    parent: "engine-block",
    ex: [0, -0.06, 0.16],
    blurb: "Cable-operated clutch. There is no hydraulic slave on the base T-5 car. Free play at the pedal is the adjustment. Too tight burns the disc. Too loose won't release.",
    specs: [{ label: "Release", value: "Cable and quadrant, firewall" }],
    checks: [
      "A pedal that stays on the floor is a broken quadrant or a frayed cable, not a master cylinder. You don't have a master cylinder.",
      "Chatter on takeoff is glazing or oil on the disc. Oil means the rear main or the input-shaft seal. A new disc on a leaking seal comes back.",
      "The pilot bearing whines with the pedal down and the gearbox in neutral. Release the pedal and it goes away."
    ],
    keywords: ["clutch", "cable", "quadrant", "pilot"]
  },
  {
    id: "flywheel",
    name: "Flywheel",
    system: "engine",
    stage: 5,
    parent: "engine-block",
    ex: [0, -0.1, 0.22],
    blurb: "Flywheel on the back of the crank. The starter ring is on it. Hot spots and cracks are why a new clutch still chatters.",
    checks: [
      "Check the ring gear where the starter engages. A chewed ring eats the next starter.",
      "Resurface or replace if it's blued. Bolts are one-time if the manual says so \u2014 don't reuse a bolt you're unsure of."
    ],
    keywords: ["flywheel", "ring gear"]
  },
  {
    id: "torque-converter",
    name: "Torque converter",
    system: "driveline",
    stage: 4,
    parent: "trans",
    ex: [0, 0, -0.2],
    blurb: "Converter on the 4R70W. It has to be fully seated on the pump before the trans goes against the block. A converter that is one tooth out breaks the pump the first time it cranks.",
    checks: [
      "Three clunks as it slides back onto the input, stator, and pump. If it doesn't sit flush, stop.",
      "Fill the converter before install if you can. A dry pump is a 30-second failure."
    ],
    keywords: ["torque converter", "automatic"]
  },
  {
    id: "vss",
    name: "Vehicle speed sensor",
    system: "electrical",
    stage: 4,
    parent: "trans",
    ex: [0, -0.12, 0.14],
    circuit: "sensor",
    blurb: "VSS in the tailhousing. The speedometer and the PCM both read it. On an automatic it also affects shift scheduling.",
    checks: [
      "A dead speedo with a working odometer, or the reverse, depends on the cluster. A speedo that drops to zero and comes back is often this sensor or the connector, which gets soaked.",
      "The driven gear is plastic and sheds teeth. If the sensor tests fine and the speed is wrong, look at the gear."
    ],
    keywords: ["vss", "speedometer", "speed sensor"]
  },
  {
    id: "engine-block",
    name: "3.8L block",
    system: "engine",
    stage: 3,
    ex: [0, -0.62, -0.18],
    blurb: "Essex 3.8L (232 cu in) OHV V6, 90-degree, iron block, iron heads. 2001 rating is 193 hp at 5,500 rpm and 225 lb-ft at 2,800. Compression 9.4:1. Firing order 1-4-2-5-3-6. Passenger bank is cylinders 1-2-3 front to rear. Driver bank is 4-5-6 front to rear.",
    specs: [
      { label: "Displacement", value: "3.8 L / 232 cu in" },
      { label: "Layout", value: "OHV, 2-valve, EDIS waste-spark" },
      { label: "Fuel", value: "87 octane, returnless SEFI" },
      { label: "Firing order", value: "1-4-2-5-3-6" },
      { label: "Compression", value: "9.4:1" },
      { label: "Oil", value: "5W-20, 4.7 L (5.0 qt) with filter" },
      { label: "Coolant", value: "11.2 L (11.8 qt). Green or Premium Gold \u2014 don't mix them casually" }
    ],
    checks: [
      "A rod knock is low, at hot idle, and it follows engine speed in neutral. A tick at the top is usually a lifter, an exhaust leak, or a plug wire.",
      "Milkshake on the dipstick or the oil fill is the lower intake gasket until you prove otherwise. That is the famous failure on this engine.",
      "The block is iron. It will outlast the intake gaskets, the valve-cover gaskets, and the cooling system."
    ],
    keywords: ["engine", "3.8", "essex", "block", "firing order", "compression"]
  },
  {
    id: "head-l",
    name: "Driver head (cyl 4-5-6)",
    system: "engine",
    stage: 4,
    parent: "engine-block",
    ex: [-0.3, 0.1, 0],
    blurb: "Driver-side iron head. Cylinders 4, 5, 6 from front to rear. Pushrods, rockers, and the plugs for this bank live here.",
    checks: [
      "A miss on one cylinder on this bank with a good plug and wire is compression or an injector. Don't pull the head for a fouled plug.",
      "Head gaskets are not the first coolant leak on a 3.8. The lower intake is. Prove the intake before the head comes off."
    ],
    keywords: ["head", "cylinder 4", "cylinder 5", "cylinder 6"]
  },
  {
    id: "head-r",
    name: "Passenger head (cyl 1-2-3)",
    system: "engine",
    stage: 4,
    parent: "engine-block",
    ex: [0.3, 0.1, 0],
    blurb: "Passenger-side iron head. Cylinders 1, 2, 3 from front to rear.",
    checks: [
      "Same rule: intake gasket before head gasket.",
      "The exhaust manifold on this side cracks at the ends and ticks when cold. A tick that leaves when hot is often that manifold, not a lifter."
    ],
    keywords: ["head", "cylinder 1", "cylinder 2", "cylinder 3"]
  },
  {
    id: "valve-cover-l",
    name: "Driver valve cover",
    system: "engine",
    stage: 4,
    parent: "head-l",
    ex: [-0.18, 0.14, 0],
    blurb: "Driver valve cover. These leak onto the exhaust manifold and the plug wires. The leak smells like oil burning and looks like a miss.",
    fasteners: [
      { name: "Cover bolt", thread: "Small, confirm length", torque: "Low, crisscross. A cheater bar cracks the cover." }
    ],
    checks: [
      "Clean it, run it, watch the seam. A wet plug well is this gasket.",
      "Don't pile silicone on a rubber gasket. It pushes the gasket out and leaks worse."
    ],
    keywords: ["valve cover", "oil leak"]
  },
  {
    id: "valve-cover-r",
    name: "Passenger valve cover",
    system: "engine",
    stage: 4,
    parent: "head-r",
    ex: [0.18, 0.14, 0],
    blurb: "Passenger valve cover. The PCV often pulls from this cover or the intake. A plugged PCV pushes oil out of both covers.",
    checks: [
      "Fix the PCV before the third gasket. Pressure finds a way out.",
      "Same low-torque rule. The baffle inside breaks and then the PCV slurps oil."
    ],
    keywords: ["valve cover", "pcv"]
  },
  {
    id: "intake-lower",
    name: "Lower intake",
    system: "engine",
    stage: 4,
    parent: "engine-block",
    ex: [0, 0.26, 0],
    blurb: "Lower intake manifold. The gasket under it is the job this engine is known for. Coolant and oil meet there. When the gasket fails you get milkshake, unexplained coolant loss, and a sweet exhaust.",
    checks: [
      "Before you pull it: look at the oil, the coolant, and whether it overheats with the cabin heat on. Confirm it's mixing, not just a dirty cap.",
      "The bolts are a sequence, several passes, from the center out. The shop manual has the order. Don't freelance it.",
      "Replace the thermostat and the water-neck gasket while you're here. You already drained it.",
      "Torque-to-yield bolts get replaced if the manual says they're single-use. When in doubt, new bolts are cheaper than the comeback."
    ],
    keywords: ["intake", "milkshake", "coolant in oil", "gasket"]
  },
  {
    id: "intake-gasket",
    name: "Lower intake gasket",
    system: "engine",
    stage: 4,
    parent: "engine-block",
    ex: [0, 0.16, 0.24],
    blurb: "The gasket itself. On this 3.8 it is the part that fails, not a mysterious head gasket. Coolant passages and oil passages share the sealing surface.",
    checks: [
      "Surfaces must be clean and flat. A razor and a careful hand. A rotary disc on the aluminum intake eats the sealing face.",
      "Follow the gasket maker's metal-or-rubber note. Extra silicone in a coolant port becomes a plugged heater core.",
      "Refill and bleed. An air pocket after this job overheats the engine you just sealed and warps your afternoon."
    ],
    keywords: ["intake gasket", "milkshake", "coolant"]
  },
  {
    id: "intake-upper",
    name: "Upper intake",
    system: "engine",
    stage: 4,
    parent: "intake-lower",
    ex: [0, 0.24, -0.06],
    blurb: "Upper plenum. The throttle body bolts to the front of it. Vacuum leaks here are a high idle and a lean code.",
    checks: [
      "Spray brake cleaner is a crude test and a fire hazard near a hot manifold. A smoke machine is the grown-up version.",
      "The gasket is a repeat job if the bolts are overtightened and the plastic or aluminum warps. Low torque."
    ],
    keywords: ["plenum", "upper intake", "vacuum"]
  },
  {
    id: "throttle-body",
    name: "Throttle body",
    system: "engine",
    stage: 4,
    parent: "intake-upper",
    ex: [0, 0.06, -0.2],
    blurb: "Cable throttle body. No electronic throttle on this car. The plate, the TPS, and the IAC all sit here.",
    checks: [
      "Carbon on the plate causes a hang in idle. Clean it with throttle-body cleaner with the IAC protected. Don't scrape the plate with a screwdriver.",
      "The cable should return on its own. A sticky cable is the cruise dump or a frayed strand, and it is a safety item.",
      "Set the minimum air the way the manual says. Backing the stop screw out to 'fix' a high idle hides an IAC or a vacuum leak."
    ],
    keywords: ["throttle", "idle", "cable"]
  },
  {
    id: "iac",
    name: "Idle air control",
    system: "electrical",
    stage: 5,
    parent: "throttle-body",
    ex: [-0.12, 0.08, 0],
    circuit: "sensor",
    blurb: "IAC valve on the throttle body. The PCM parks the idle with this pintle. Carbon sticks it.",
    checks: [
      "A hunting idle or a stall as you come to a stop is this valve or a vacuum leak. Clean the passage, don't twist the pintle with pliers.",
      "It has to be installed at the right extension or it ratchets itself to death on the first start. Follow the install note."
    ],
    keywords: ["iac", "idle", "stall"]
  },
  {
    id: "thermostat",
    name: "Thermostat",
    system: "cooling",
    stage: 4,
    parent: "intake-lower",
    ex: [0, 0.14, -0.16],
    blurb: "Thermostat in the housing at the front of the intake. A lazy one runs the engine cold and the fuel trims go rich. A stuck-shut one overheats in minutes.",
    checks: [
      "Replace the gasket or O-ring with it. The housing bolts are short and strip the aluminum if you overtighten them.",
      "Bleed the air. The 3.8 holds a pocket at this housing. Heat full hot, front of the car up a little, cap off, until the level stays.",
      "The weep hole and the jiggle pin have an up. Install it the way the part is marked."
    ],
    keywords: ["thermostat", "overheat", "runs cold"]
  },
  {
    id: "oil-pan",
    name: "Oil pan",
    system: "engine",
    stage: 4,
    parent: "engine-block",
    ex: [0, -0.34, 0],
    blurb: "Oil pan and the drain. Capacity with the filter is 5.0 quarts of 5W-20. The pan rail is a slow leak people blame on the rear main.",
    specs: [
      { label: "Oil", value: "SAE 5W-20, 4.7 L (5.0 qt) with FL-400S" },
      { label: "Filter", value: "Motorcraft FL-400S" }
    ],
    fasteners: [
      {
        name: "Drain plug",
        thread: "Confirm on the pan before you buy a kit",
        torque: "Gentle, with a new washer. Stripped pans are a 3.8 tradition."
      },
      { name: "Rail bolt", thread: "Small", torque: "Low, even sequence. Silicone only where the manual calls for it." }
    ],
    checks: [
      "Wipe the drain plug, run it, and look again. A weeping plug is the washer or the threads, not 'snug it until it stops'.",
      "If the plug is already rounded, a new pan or a proper insert beats the next oil change with vice grips.",
      "Rear-main leaks drip off the back of the pan. Pan-rail leaks wet the rail. Know which one you're seeing before the trans comes out."
    ],
    keywords: ["oil", "drain", "5w-20", "pan"]
  },
  {
    id: "oil-filter",
    name: "Oil filter",
    system: "engine",
    stage: 4,
    parent: "oil-pan",
    ex: [-0.2, -0.06, 0],
    blurb: "Motorcraft FL-400S. Thread is 3/4-16. It sits where you will burn your arm if the engine is hot. Plan the angle.",
    specs: [{ label: "Part", value: 'FL-400S \xB7 3/4"-16' }],
    fasteners: [
      { name: "Filter", thread: '3/4"-16', torque: "Gasket oiled, hand tight, then about 3/4 turn. Not a wrench until it groans." }
    ],
    checks: [
      "The old gasket sticks to the adapter. A double gasket dumps 5 quarts on the first start. Look with a light.",
      "Prefill the filter if you can keep it upright on the way in. A dry start is a dry start."
    ],
    keywords: ["oil filter", "fl-400s"]
  },
  {
    id: "front-cover",
    name: "Timing cover",
    system: "engine",
    stage: 4,
    parent: "engine-block",
    ex: [0, 0, -0.28],
    blurb: "Front cover over the timing chain. It leaks at the seal and at the oil-pan joint. The crank sensor reads a wheel just behind this area.",
    checks: [
      "A leak at the balancer is the seal. A leak at the pan corner is the pan-to-cover joint. Different jobs.",
      "The cover bolts are different lengths. They go back where they came from or they punch the cover."
    ],
    keywords: ["timing cover", "front cover"]
  },
  {
    id: "balancer",
    name: "Harmonic balancer",
    system: "engine",
    stage: 4,
    parent: "front-cover",
    ex: [0, 0, -0.18],
    blurb: "Harmonic balancer on the nose of the crank. The rubber between hub and ring separates with age. A wobble here throws the belt and lies to the crank sensor.",
    checks: [
      "Look at the rubber. If the ring has walked forward, replace it. Don't 'send it'.",
      "Pull it with a puller that uses the threaded holes. A jaw puller on the ring finishes the separation.",
      "The bolt is tight. An impact and a holder, not a wrench braced on the radiator."
    ],
    keywords: ["balancer", "harmonic", "dampener"]
  },
  {
    id: "water-pump",
    name: "Water pump",
    system: "cooling",
    stage: 4,
    parent: "front-cover",
    ex: [0, 0.06, -0.16],
    blurb: "Water pump on the front cover, with the clutch fan on the snout. The weep hole is under the snout. Coolant there is the pump.",
    checks: [
      "A weep that only shows after shutdown is still the pump. The hole is doing its job.",
      "The gasket surface needs to be clean. Silicone in the coolant passage is how you plug a radiator.",
      "Turn the snout. Rough or noisy with the belt off is the bearing, and the fan clutch is a separate part."
    ],
    keywords: ["water pump", "weep", "coolant"]
  },
  {
    id: "fan-clutch",
    name: "Fan clutch",
    system: "cooling",
    stage: 4,
    parent: "engine-block",
    ex: [0, 0.04, -0.42],
    blurb: "Thermal fan clutch on the water pump. The base 3.8 moves air with this fan, not a GT electric setup. It should roar for a minute when hot and then quiet down on the road.",
    checks: [
      "A fan that never pulls air overheats in traffic and is fine at 60. That's a freewheeling clutch.",
      "A fan that roars all the time is seized. It eats horsepower and belts.",
      "The fan nuts are left-hand on some Ford clutches. Confirm before you snap a stud. Spin direction is stamped."
    ],
    keywords: ["fan", "clutch fan", "overheat", "traffic"]
  },
  {
    id: "ckp",
    name: "Crankshaft sensor",
    system: "electrical",
    stage: 4,
    parent: "front-cover",
    ex: [0.14, -0.1, -0.12],
    circuit: "ignition",
    blurb: "CKP at the front of the block. EDIS and the PCM need this pulse. A dead sensor cranks, fires nothing, and usually sets a code after a long crank.",
    checks: [
      "Oil-soaked connector is the usual failure, right after a front-cover leak. Clean and dry it before you buy a sensor.",
      "The air gap is small. Don't pry the sensor against the wheel. A bent wheel makes a sensor that 'fails' at certain rpm.",
      "A no-start that is spark-and-fuel dead at the same time is often this sensor or the PCM power, not six bad plugs."
    ],
    keywords: ["ckp", "crank sensor", "no start"]
  },
  {
    id: "alternator",
    name: "Alternator",
    system: "electrical",
    stage: 4,
    parent: "engine-block",
    ex: [0.34, 0.02, -0.04],
    circuit: "power",
    blurb: "Alternator on the passenger side of the engine, belt driven. Charging target is roughly 13.5\u201314.5 V at idle with loads on. The big stud is B+. The small wires are the turn-on and the sense.",
    specs: [{ label: "Charge", value: "About 13.5\u201314.5 V, engine running, loads on" }],
    fasteners: [
      { name: "B+ nut", thread: "Stud nut, smaller than it looks", torque: "Snug. A spinning stud means stop." }
    ],
    checks: [
      "Voltage at the battery, not at a guess. Under 13 with a good belt means the alternator, the B+ cable, or the fuse in the power box.",
      "A whine that follows rpm and changes when you switch the blower is often the alternator diodes, or a ground.",
      "The battery has to be charged enough to excite it. A stone-dead battery can make a good alternator look dead."
    ],
    keywords: ["alternator", "charging", "battery light", "voltage"]
  },
  {
    id: "ps-pump",
    name: "Power steering pump",
    system: "engine",
    stage: 4,
    parent: "engine-block",
    ex: [-0.32, 0.06, 0],
    blurb: "Pump on the driver side. The 3.8 uses MERCON ATF in this pump. Keep it in the FULL HOT range on the dipstick.",
    specs: [{ label: "Fluid", value: "MERCON ATF. Not a universal PSF unless it actually meets the spec." }],
    checks: [
      "A groan in the morning that goes away is often low fluid or air, or a hose collapsing. Look at the level hot.",
      "The pulley is a press fit. Don't hammer it on. A pulled pulley that was hammered whines forever.",
      "Leaks at the fitting are the hose O-ring. Tighten the fitting, don't crush it."
    ],
    keywords: ["power steering", "ps pump", "mercon"]
  },
  {
    id: "ac-compressor",
    name: "A/C compressor",
    system: "cooling",
    stage: 4,
    parent: "engine-block",
    ex: [0.3, -0.16, 0.12],
    blurb: "R-134a compressor. The clutch is on the front. The CCRM feeds the clutch. A system that is empty will not engage, on purpose.",
    specs: [{ label: "Refrigerant", value: "R-134a. Pressures depend on shop temp and a gauge set." }],
    checks: [
      "If the clutch never clicks, check pressure and the request from the dash before the compressor gets condemned. Low charge opens the switch.",
      "A black dust around the clutch is a slipping clutch. That cooks itself and then the belt.",
      "Oil type matters if the system is opened. Pag oil for R-134a, the amount the manual lists, not a glug."
    ],
    keywords: ["ac", "compressor", "r134a", "clutch"]
  },
  {
    id: "starter",
    name: "Starter",
    system: "electrical",
    stage: 4,
    parent: "engine-block",
    ex: [0.26, -0.2, 0.06],
    circuit: "start",
    blurb: "Starter low on the passenger side of the block. It engages the flywheel ring. A single click is often this solenoid or a weak battery. A rapid click is the battery or the cables.",
    checks: [
      "Voltage at the big stud while cranking tells you if the cable is the problem. Under about 10 V at the stud with a good battery means the cable or the connection.",
      "A starter that spins and doesn't engage has a bad bendix or a chewed ring gear. Pull it and look at both.",
      "Heat-soak no-crank that fixes itself in 20 minutes is a classic tired starter on these cars."
    ],
    keywords: ["starter", "no crank", "click"]
  },
  {
    id: "coil-pack",
    name: "EDIS coil pack",
    system: "electrical",
    stage: 4,
    parent: "engine-block",
    ex: [0.08, 0.22, -0.08],
    circuit: "ignition",
    blurb: "One coil pack, waste spark. Three coils, six plugs. A failed tower usually kills two cylinders, the paired ones, not one. A miss on a single cylinder is more often the plug, the wire, the injector, or compression.",
    specs: [
      { label: "System", value: "EDIS waste-spark" },
      { label: "Firing order", value: "1-4-2-5-3-6" }
    ],
    checks: [
      "Swap wires on the pack only as a test, and put them back. A miss that moves with the wire is the wire or the coil tower. A miss that stays is the cylinder.",
      "Cracks in the plastic and white carbon tracks are the pack. Dielectric grease in the boot helps the next one.",
      "Don't unplug coils with the engine running to 'find the miss' unless you enjoy cooking drivers and getting shocked."
    ],
    keywords: ["coil", "edis", "misfire", "waste spark"]
  },
  {
    id: "manifold-l",
    name: "Driver exhaust manifold",
    system: "exhaust",
    stage: 4,
    parent: "head-l",
    ex: [-0.2, -0.08, 0],
    blurb: "Driver exhaust manifold. These crack and leak at the gasket. A cold tick that goes away is the usual clue.",
    fasteners: [
      { name: "Manifold stud", thread: "Often seized in the iron head", torque: "Broken studs are the job. Use heat and patience, not a cheater on a 6-point that's already slipping." }
    ],
    checks: [
      "Feel for a puff at the gasket with a cold start, hands clear of the belt.",
      "A broken stud left in the head can be extracted. A snapped easy-out cannot. Drill straight."
    ],
    keywords: ["manifold", "tick", "exhaust leak"]
  },
  {
    id: "manifold-r",
    name: "Passenger exhaust manifold",
    system: "exhaust",
    stage: 4,
    parent: "head-r",
    ex: [0.2, -0.08, 0],
    blurb: "Passenger manifold. Same crack and stud story. The upstream oxygen sensor is near this collector.",
    checks: [
      "Don't replace the O2 sensor for a tick. Fix the leak. A leak ahead of the sensor makes it lie and set a fuel-trim code."
    ],
    keywords: ["manifold", "exhaust"]
  },
  {
    id: "dipstick",
    name: "Oil dipstick",
    system: "engine",
    stage: 4,
    parent: "engine-block",
    ex: [-0.14, 0.22, 0.05],
    blurb: "Dipstick and tube. The 5-quart fill is real; the stick is how you confirm it. Check on level ground, engine off, after it has sat a minute.",
    checks: [
      "A tube that is loose at the block drips and looks like a rear-main leak.",
      "Overfull is as bad as low on this engine. It foams and the lifters tick, and the seals push out."
    ],
    keywords: ["dipstick", "oil level"]
  },
  {
    id: "pcv",
    name: "PCV valve",
    system: "engine",
    stage: 4,
    parent: "valve-cover-r",
    ex: [0.06, 0.12, 0],
    blurb: "Motorcraft EV-152. It meters crankcase vapor into the intake. A stuck-shut valve pushes oil out of the covers and the rear main.",
    specs: [{ label: "Part", value: "EV-152" }],
    checks: [
      "It should rattle. A rattle doesn't mean the spring is right, but a silent valve is done.",
      "The elbow and hose crack. A brittle hose is a vacuum leak and a high idle.",
      "Replace it when you do the intake. It's right there and it's cheap."
    ],
    keywords: ["pcv", "ev-152"]
  },
  {
    id: "belt",
    name: "Serpentine belt",
    system: "engine",
    stage: 4,
    parent: "engine-block",
    ex: [0, 0.04, -0.55],
    blurb: "One belt drives the accessories. The routing sticker is on the radiator support. Cracks across the ribs, glaze, or a belt that has started to walk mean replace it \u2014 and look at the tensioner.",
    checks: [
      "A chirp on a cold start is usually a pulley, not 'belt dressing'. Dressing makes it worse.",
      "Ribs out versus ribs in matters. The sticker is the map. A backwards belt screams.",
      "Replace the tensioner if the belt was shredded. The new belt will follow the old one off."
    ],
    keywords: ["belt", "serpentine", "squeal"]
  },
  {
    id: "tensioner",
    name: "Belt tensioner",
    system: "engine",
    stage: 4,
    parent: "engine-block",
    ex: [-0.18, 0.12, -0.36],
    blurb: "Spring-loaded tensioner and its pulley. A rattle at idle that follows engine speed, with a belt that oscillates, is this.",
    checks: [
      "Watch the tensioner with the engine running. It should be steady. A dancing arm is a weak spring or a bad pulley bearing.",
      "The pulley bearing should spin smooth with the belt off. A growl is the bearing. Replace the pulley or the whole tensioner, whichever is actually worn."
    ],
    keywords: ["tensioner", "idler", "pulley"]
  },
  {
    id: "crank",
    name: "Crankshaft",
    system: "engine",
    stage: 5,
    parent: "engine-block",
    ex: [0, -0.36, 0.12],
    blurb: "Crankshaft in the block. Main bearings and rod journals. A deep knock that is worse under load is here. This is not a driveway bearing job without a stand and plastigage.",
    checks: [
      "Confirm it's a knock and not a broken balancer, a loose converter bolt, or a rod itself hitting the pan.",
      "If you're this deep, measure. New bearings on an unmeasured journal are a guess."
    ],
    keywords: ["crank", "bearing", "knock"]
  },
  {
    id: "pistons",
    name: "Pistons",
    system: "engine",
    stage: 5,
    parent: "engine-block",
    ex: [0, 0.5, 0],
    blurb: "Six pistons. A slap when cold that goes away can be skirts. A slap that stays, with smoke, is rings or a broken ring land. Compression and a leak-down tell you before the head comes off.",
    checks: [
      "Compression across all six, throttle open, same cranking speed. One low cylinder next to another low cylinder can be a head gasket between them. One low cylinder is a valve, a ring, or a cracked plug.",
      "Bore this block only if it needs it. These engines get hurt by intake gaskets long before the pistons are done."
    ],
    keywords: ["piston", "compression", "slap"]
  },
  {
    id: "rods",
    name: "Connecting rods",
    system: "engine",
    stage: 5,
    parent: "engine-block",
    ex: [0.18, 0.12, 0.16],
    blurb: "Rods between the pistons and the crank. A rod knock is sharper than a main knock and often follows one cylinder.",
    checks: [
      "Disable that cylinder's injector or plug as a test only if you know the oil isn't already full of metal. If the knock changes, you've found the hole.",
      "Rod bolts are not reusable if they're torque-to-yield. The manual is specific. New bolts are part of the job."
    ],
    keywords: ["rod", "knock"]
  },
  {
    id: "cam",
    name: "Camshaft",
    system: "engine",
    stage: 5,
    parent: "engine-block",
    ex: [0, 0.38, 0.08],
    blurb: "Cam in the valley of the block, OHV. It moves the lifters, pushrods, and rockers. A wiped lobe ticks and that cylinder goes soft.",
    checks: [
      "A tick that is one cylinder, with low vacuum on that intake stroke, can be a lobe. A borescope through the oil fill sometimes shows it without a teardown.",
      "New cam, new lifters. Old lifters on a new cam wipe it immediately."
    ],
    keywords: ["cam", "lobe", "tick"]
  },
  {
    id: "timing-chain",
    name: "Timing chain",
    system: "engine",
    stage: 5,
    parent: "engine-block",
    ex: [0, 0.04, -0.36],
    blurb: "Single chain at the front of the cam and crank. Slack retards the cam. A rattle at the cover on start, and a lazy engine, is stretch.",
    checks: [
      "If the cover is off, replace the chain and the gears as a set. A new chain on a hooked gear is still slack.",
      "Line the marks up the way the manual draws them, not the way a forum photo from a 5.0 shows them."
    ],
    keywords: ["timing chain"]
  },
  {
    id: "oil-pump",
    name: "Oil pump",
    system: "engine",
    stage: 5,
    parent: "engine-block",
    ex: [0, -0.22, -0.3],
    blurb: "Oil pump at the front of the block, driven off the distributor-less cam drive. Low oil pressure when hot, with the level correct and the bearings not knocking yet, can be the pump or the pickup tube.",
    checks: [
      "A gauge in the port beats the dash light. The light is a switch, and it lies by being late.",
      "The pickup tube O-ring, if it has one, sucks air and the pressure drops at idle. Look at it whenever the pan is off."
    ],
    keywords: ["oil pump", "oil pressure"]
  },
  {
    id: "valves-l",
    name: "Driver valves",
    system: "engine",
    stage: 5,
    parent: "head-l",
    ex: [-0.1, 0.22, 0],
    blurb: "Intake and exhaust valves in the driver head, cylinders 4-5-6. They are not adjustable with a screw the way a small-block Chevy is. Geometry is pushrod length and rocker.",
    checks: [
      "A burned exhaust valve is a dead cylinder that leak-down hears in the tailpipe.",
      "Don't lap a valve and call it a valve job if the guide is loose. It'll come back."
    ],
    keywords: ["valve"]
  },
  {
    id: "valves-r",
    name: "Passenger valves",
    system: "engine",
    stage: 5,
    parent: "head-r",
    ex: [0.1, 0.22, 0],
    blurb: "Valves for cylinders 1-2-3.",
    checks: ["Same leak-down listening: intake tract, exhaust, or crankcase tells you where the air left."],
    keywords: ["valve"]
  },
  plugs("plugs-l", "Plugs 4-5-6", "head-l", [-0.18, 0.02, 0], "Driver bank, cylinders 4-5-6, front of the engine first"),
  plugs("plugs-r", "Plugs 1-2-3", "head-r", [0.18, 0.02, 0], "Passenger bank, cylinders 1-2-3, front of the engine first"),
  {
    id: "pushrods",
    name: "Pushrods",
    system: "engine",
    stage: 5,
    parent: "engine-block",
    ex: [0, 0.42, 0.04],
    blurb: "Pushrods from the lifters up to the rockers. A bent one is a bent one. They don't straighten.",
    checks: [
      "Roll each one on glass. A bent rod rocks. That cylinder will tick and be soft.",
      "Keep them in order if you're reusing them. They wear into their rockers."
    ],
    keywords: ["pushrod"]
  },
  {
    id: "rockers-l",
    name: "Driver rockers",
    system: "engine",
    stage: 5,
    parent: "head-l",
    ex: [-0.08, 0.16, 0],
    blurb: "Rocker arms on the driver head. A loose pedestal ticks. A wiped tip ticks louder.",
    checks: [
      "Torque the pedestals evenly. One loose bolt is a tick people chase with oil additives.",
      "Look at the pushrod cup. If it's egg-shaped, the rocker is done."
    ],
    keywords: ["rocker"]
  },
  {
    id: "rockers-r",
    name: "Passenger rockers",
    system: "engine",
    stage: 5,
    parent: "head-r",
    ex: [0.08, 0.16, 0],
    blurb: "Rocker arms on the passenger head.",
    checks: ["Same pedestal and cup check."],
    keywords: ["rocker"]
  },
  {
    id: "airbox",
    name: "Air box",
    system: "engine",
    stage: 3,
    ex: [-0.42, 0.28, -0.08],
    blurb: "Air cleaner housing on the driver side of the bay. Element is Motorcraft FA-1611. An oiled aftermarket filter is how these MAFs die.",
    specs: [{ label: "Element", value: "FA-1611" }],
    checks: [
      "The box has to clip shut. An open box is a vacuum leak after the MAF, which is unmetered air, which is a lean stumble.",
      "The duct to the throttle body cracks on the bottom where you can't see it. Squeeze it."
    ],
    keywords: ["air filter", "fa-1611", "airbox"]
  },
  {
    id: "maf",
    name: "MAF sensor",
    system: "electrical",
    stage: 4,
    parent: "airbox",
    ex: [0.16, 0.04, 0.08],
    circuit: "sensor",
    blurb: "Mass-air sensor in the air duct. The PCM fuels from this. Oil on the wires makes it read low, the car runs rich, and the plugs foul.",
    checks: [
      "Clean only with MAF cleaner, key off, sensor out or protected. Brake cleaner and shop rags leave film.",
      "Don't touch the wires. They break and then the cleaner gets blamed.",
      "A MAF code with a cone filter and an oiled element is the filter. Put the stock box back before you buy a sensor."
    ],
    keywords: ["maf", "mass air", "runs rich"]
  },
  {
    id: "tps",
    name: "Throttle position sensor",
    system: "electrical",
    stage: 5,
    parent: "throttle-body",
    ex: [0.1, 0.06, 0],
    circuit: "sensor",
    blurb: "TPS on the throttle shaft. A dead spot feels like a stumble at the same pedal every time. That repeatability is the clue.",
    checks: [
      "Watch the voltage sweep. It should climb smooth. A drop in the middle is the sensor.",
      "Don't blast it with cleaner down the shaft and into the pot."
    ],
    keywords: ["tps", "stumble"]
  },
  {
    id: "ect",
    name: "Coolant temp sensor",
    system: "electrical",
    stage: 4,
    parent: "intake-lower",
    ex: [0.12, 0.1, -0.08],
    circuit: "sensor",
    blurb: "ECT for the PCM, not the gauge sender if the car has both. A sensor that reads cold all the time runs the engine rich and the fan logic wrong.",
    checks: [
      "A cold reading with a hot engine is this sensor or its connector, which lives in coolant mist when the intake leaks.",
      "It's often plastic and it breaks when old. Have the new one ready before the old one comes out, because the coolant follows it."
    ],
    keywords: ["ect", "temp sensor", "runs rich"]
  },
  {
    id: "radiator",
    name: "Radiator",
    system: "cooling",
    stage: 3,
    ex: [0, 0.22, -0.58],
    blurb: "Crossflow radiator ahead of the fan. Capacity of the whole system is 11.8 quarts. Coolant is Motorcraft green or Premium Gold yellow. Don't mix colors because the bottle was handy.",
    specs: [
      { label: "Capacity", value: "11.2 L (11.8 qt) for the 3.8" },
      { label: "Coolant", value: "Premium green or Premium Gold. Flush if you switch." }
    ],
    checks: [
      "Tanks crack at the crimp. A wet right tank is the radiator, not the water pump.",
      "The cap holds pressure. A cap that doesn't hold 16 psi (confirm the cap) boils low and looks like a bad radiator.",
      "Stop-leak is how heater cores die. Don't pour it in."
    ],
    keywords: ["radiator", "coolant", "overheat"]
  },
  {
    id: "exhaust-l",
    name: "Driver downpipe",
    system: "exhaust",
    stage: 3,
    ex: [-0.12, -0.32, 0],
    blurb: "Pipe off the driver manifold toward the Y. The base 3.8 is a single exhaust after the Y, not dual.",
    checks: [
      "Leaks at the flange puff cold and tick. New hardware, not the old studs reused until they snap in the car."
    ],
    keywords: ["downpipe", "exhaust"]
  },
  {
    id: "exhaust-r",
    name: "Passenger downpipe",
    system: "exhaust",
    stage: 3,
    ex: [0.12, -0.32, 0.05],
    blurb: "Passenger pipe into the catalytic converter. The upstream O2 sensor is in this stream.",
    checks: ["A leak here ahead of the O2 sensor drives fuel trims. Fix the leak before chasing injectors."],
    keywords: ["downpipe"]
  },
  {
    id: "cat",
    name: "Catalytic converter",
    system: "exhaust",
    stage: 3,
    ex: [0.08, -0.3, 0.12],
    blurb: "Underfloor converter on the single exhaust. The downstream O2 sensor watches it. A rattle inside is a broken brick. A brick that melted plugs the pipe and the car falls on its face when hot.",
    checks: [
      "A vacuum gauge that dies at cruise, or a car that only runs cold, can be a plugged cat. A temperature check inlet versus outlet is the old-school confirm.",
      "Don't cut it out for a 'test pipe' and drive it. It's a federal emissions device, and the downstream sensor will set a code anyway."
    ],
    keywords: ["catalytic", "cat", "plugged"]
  },
  {
    id: "muffler",
    name: "Muffler and tip",
    system: "exhaust",
    stage: 3,
    ex: [0.2, -0.22, 0.28],
    blurb: "Single muffler, tip on the passenger side of the rear bumper. That single tip is how you tell a base car from a GT at a glance.",
    checks: [
      "A rot hole at the seam is the rasp. Clamps have a direction. A clamp that crushes the pipe leaks next to the repair.",
      "Clearance to the fuel tank and the brake cable. A 'close enough' exhaust melts a cable or ticks on the tank."
    ],
    keywords: ["muffler", "tip"]
  },
  {
    id: "o2-up",
    name: "Upstream O2 sensor",
    system: "exhaust",
    stage: 3,
    ex: [0.16, -0.12, 0.02],
    circuit: "sensor",
    blurb: "Upstream oxygen sensor, ahead of the converter. This is the one the PCM fuels from. Thread is the usual M18\xD71.5.",
    fasteners: [
      { name: "Sensor", thread: "M18 \xD7 1.5", torque: "About 30 lb-ft. Anti-seize on the threads only, never the tip." }
    ],
    checks: [
      "A lazy sensor sets fuel-trim codes and a rich or lean smell. Graph it if you can. A flat line is dead. A slow wave is lazy.",
      "The connector heat-cycles. Wiggle it. A sensor that comes back when you move the plug is the harness, not the element.",
      "Four wires versus one: this era is heated. The heater circuit has its own fuse and code."
    ],
    keywords: ["o2", "oxygen", "fuel trim"]
  },
  {
    id: "o2-down",
    name: "Downstream O2 sensor",
    system: "exhaust",
    stage: 3,
    ex: [0.1, -0.1, 0.16],
    circuit: "sensor",
    blurb: "Downstream sensor after the converter. It monitors the cat. It does not trim fuel the way the upstream sensor does.",
    fasteners: [
      { name: "Sensor", thread: "M18 \xD7 1.5", torque: "Same as the upstream. Anti-seize on threads only." }
    ],
    checks: [
      "A cat code is not automatically a dead cat. A lazy downstream sensor, an exhaust leak, or a rich upstream condition all set it.",
      "Don't swap up and down unless the connectors and heaters match. They often don't."
    ],
    keywords: ["o2", "downstream", "catalyst"]
  },
  {
    id: "fuel-tank",
    name: "Fuel tank",
    system: "fuel",
    stage: 3,
    ex: [0, -0.42, 0.12],
    blurb: "Plastic tank under the trunk floor, about 15.7 gallons (2R3Z-9002-AB on cars built after 12/27/99, not the Cobra tank). Returnless: the pump, the sender, and the regulator live in the tank. The straps, filler neck, grommet, shield, and charcoal canister are separate pieces on this assembly.",
    specs: [
      { label: "Capacity", value: "15.7 gal" },
      { label: "System", value: "Returnless SEFI" }
    ],
    checks: [
      "A tank that was run empty kills pumps. If you drop it, replace the strainer. The sock is often the whole problem.",
      "The lock ring needs a proper tool or a careful brass drift. A screwdriver through the ring is how sending units crack.",
      "Support it. A plastic tank full of fuel is heavier than it looks and it cracks when it hits the ground."
    ],
    keywords: ["tank", "fuel", "gas tank"]
  },
  {
    id: "tank-strap-l",
    name: "Driver tank strap",
    system: "fuel",
    stage: 3,
    parent: "fuel-tank",
    ex: [-0.38, 0.18, 0],
    blurb: "Driver tank strap, F8ZZ-9092-AA. Two straps hold the plastic tank. The rear passenger bolt and the front bolts are 13 mm.",
    specs: [{ label: "Part", value: "F8ZZ-9092-AA" }],
    fasteners: [{ name: "Strap bolt", thread: "13 mm head", qty: "1 this strap" }],
    checks: [
      "Hold the tank before the last bolt comes out. It drops.",
      "A rusty strap looks fine until the tank is full. If the edges are flaking, replace the strap with the tank job."
    ],
    keywords: ["strap", "tank strap", "gas tank"]
  },
  {
    id: "tank-strap-r",
    name: "Passenger tank strap",
    system: "fuel",
    stage: 3,
    parent: "fuel-tank",
    ex: [0.38, 0.18, 0],
    blurb: "Passenger tank strap, F8ZZ-9092-AB. Same job as the driver strap. The 13 mm bolts are the ones you loosen to lower the tank.",
    specs: [{ label: "Part", value: "F8ZZ-9092-AB" }],
    fasteners: [{ name: "Strap bolt", thread: "13 mm head", qty: "1 this strap" }],
    checks: ["Swing the strap down by hand after the bolt is out. Don't pry it off the tank."],
    keywords: ["strap", "tank strap"]
  },
  {
    id: "tank-shield",
    name: "Tank shield",
    system: "fuel",
    stage: 3,
    parent: "fuel-tank",
    ex: [0, -0.22, 0],
    blurb: "Protective shield under the tank. It comes down with the straps. It is not the tank, and it is not optional if it is still on the car \u2014 road debris hits this first.",
    checks: [
      "Note which way it faces before it comes off. It only fits one way around the straps.",
      "A bent shield can rub the tank. Look for a shiny spot on the plastic."
    ],
    keywords: ["shield", "tank cover", "gas tank"]
  },
  {
    id: "filler-neck",
    name: "Filler neck",
    system: "fuel",
    stage: 3,
    parent: "fuel-tank",
    ex: [-0.46, 0.28, 0.12],
    blurb: "Filler pipe from the driver-side fuel door down into the tank, 3R3Z-9034-AA on later 2001 cars. The tip breaks if you yank the tank off the neck. Push the tank toward the driver to slide it off the grommet.",
    specs: [{ label: "Part", value: "3R3Z-9034-AA" }],
    checks: [
      "Don't break the tip. That is the common mistake on this car.",
      "A loose cap or a cracked neck is an evap code, not a pump."
    ],
    keywords: ["filler", "neck", "gas cap"]
  },
  {
    id: "filler-grommet",
    name: "Filler neck grommet",
    system: "fuel",
    stage: 4,
    parent: "filler-neck",
    ex: [0, 0.12, 0],
    blurb: "Rubber grommet where the filler neck enters the tank. Replace it every time the tank comes off. The old one tears and then the new tank leaks at the neck.",
    checks: [
      "A little lube on the new grommet. Dry rubber rolls out of the hole.",
      "If the neck tip is already broken, a new grommet will not seal it."
    ],
    keywords: ["grommet", "filler"]
  },
  {
    id: "fuel-cap",
    name: "Fuel cap",
    system: "fuel",
    stage: 1,
    parent: "fuel-door",
    ex: [-0.08, 0.04, 0],
    blurb: "Sealed cap on the driver quarter. Motorcraft FC-961, or the Ford cap XU5Z-9030-JA (non-locking). A cap that clicks is doing its job. One that doesn't set an evap code.",
    specs: [{ label: "Motorcraft", value: "FC-961" }],
    checks: [
      "The cap is a part. Don't ignore a gross evap code until you have tightened it and cleared it.",
      "The tether should still be there. A missing tether means the cap lives in a pocket."
    ],
    keywords: ["gas cap", "cap", "evap"]
  },
  {
    id: "pump-gasket",
    name: "Pump hat gasket",
    system: "fuel",
    stage: 4,
    parent: "fuel-pump",
    ex: [0, 0.1, 0],
    blurb: "Gasket under the pump mounting flange, F8ZZ-9276-AA. The hat is held by six bolts with an 8 mm head. A screwdriver used as a lock-ring tool is how these hats crack \u2014 this car uses bolts, not a hammer ring.",
    specs: [{ label: "Gasket", value: "F8ZZ-9276-AA" }],
    fasteners: [{ name: "Hat bolt", thread: "8 mm head", qty: "6" }],
    checks: [
      "Blow the dirt off the top of the tank before the hat comes up. That grit falls into the tank.",
      "The gasket is one-time. A reused one weeps and smells like fuel in the trunk."
    ],
    keywords: ["gasket", "lock ring", "hat"]
  },
  {
    id: "pump-sock",
    name: "Pump strainer",
    system: "fuel",
    stage: 5,
    parent: "fuel-pump",
    ex: [0, -0.16, 0],
    blurb: "The sock on the bottom of the in-tank pump. It is the strainer. A tank that was run empty, or one full of rust, plugs this before the pump itself dies.",
    checks: [
      "If the tank is down, replace the sock. It is the cheap part of the job.",
      "A collapsed sock starves the pump and the new pump gets blamed a month later."
    ],
    keywords: ["sock", "strainer", "filter"]
  },
  {
    id: "tank-pressure",
    name: "Tank pressure sensor",
    system: "fuel",
    stage: 4,
    parent: "vapor-valve",
    ex: [0.12, 0.1, 0],
    circuit: "sensor",
    blurb: "Fuel tank pressure sensor, inline on the vapor tube above the tank. Ford services it with the vapor control valve and the vapor vent valve as one tube assembly. It is not the Schrader valve on the rail, and it is not a fuel-pressure regulator.",
    checks: [
      "The connector is small and brittle. Pull the plug, not the wires.",
      "An evap or fuel-pressure code with a good pump can be this sensor. Confirm it before you buy a pump."
    ],
    keywords: ["pressure", "transducer", "hat"]
  },
  {
    id: "evap-canister",
    name: "EVAP canister",
    system: "fuel",
    stage: 3,
    parent: "fuel-tank",
    ex: [-0.42, 0.16, -0.2],
    blurb: "Charcoal canister beside the tank, driver side. The vapor hoses land here. A saturated canister or a cracked hose is an evap code with a full tank and a good cap.",
    checks: [
      "Mark the hoses before they come off. Two of them look the same and they are not.",
      "Lower the tank only far enough to reach these clips. The driver-side vapor line is the one people rip."
    ],
    keywords: ["evap", "canister", "charcoal", "vapor"]
  },
  {
    id: "evap-purge",
    name: "EVAP purge valve",
    system: "fuel",
    stage: 3,
    ex: [0.55, 0.28, -0.35],
    circuit: "sensor",
    blurb: "The valve that regulates tank evaporation into the engine. Normally closed. The PCM duty-cycles it and intake vacuum pulls vapor from the canister. It sits in the right front inner fender, behind the splash shield. This 3.8 is returnless, so it is not a fuel-pressure regulator. Fuel pressure is set in the tank.",
    checks: [
      "A purge valve stuck open is a vacuum leak and a hunting idle. A valve that never opens stores vapor until a hose or the cap burps an evap code.",
      "Two hoses. One toward the canister, one toward the intake. Mark them before they come off.",
      "It is a two-wire solenoid. Confirm the colors in the EVTM before you pierce either wire."
    ],
    keywords: ["evap", "purge", "vapor", "solenoid", "regulator"]
  },
  {
    id: "evap-vent",
    name: "Canister vent solenoid",
    system: "fuel",
    stage: 3,
    parent: "evap-canister",
    ex: [0, 0.22, -0.12],
    circuit: "sensor",
    blurb: "Mounted on the canister in the left rear quarter. Normally open, so the canister can breathe. The PCM closes it only to seal the system for the leak test. A vent stuck closed pressure-locks the tank.",
    checks: [
      "Unplugged, you should be able to blow through it. Commanded closed, it should shut.",
      "Do not steal the purge-valve wire colors for this connector. It is a different circuit."
    ],
    keywords: ["evap", "vent", "canister", "solenoid"]
  },
  {
    id: "vapor-valve",
    name: "Fuel vapor control valve",
    system: "fuel",
    stage: 4,
    parent: "fuel-tank",
    ex: [0.28, 0.24, 0.08],
    blurb: "On top of the tank. Ford services the vapor control valve, the vapor vent valve, and the inline tank-pressure sensor as one tube. It meters vapor out of the tank and keeps liquid fuel from being pushed up the filler. The purge valve in the right front fender is the piece that regulates that vapor into the engine.",
    checks: [
      "Liquid fuel in the vapor hose means this valve is passing fuel, not just vapor. The purge valve will not fix that.",
      "Mark every hose. They look alike and they are not.",
      "The tank has to drop to replace the tube. Do it with the tank as low as you can stand."
    ],
    keywords: ["vapor valve", "vent valve", "evap", "tank"]
  },
  {
    id: "fuel-pump",
    name: "Fuel pump",
    system: "fuel",
    stage: 4,
    parent: "fuel-tank",
    ex: [0, 0.32, 0],
    circuit: "fuel",
    blurb: "In-tank pump. You should hear it run for a few seconds when the key goes to ON, if the inertia switch is set and the CCRM closes the relay. No noise and a no-start is this circuit before it is the PCM.",
    checks: [
      "Listen at the filler with the cap off. A quiet pump with power and ground at the connector is a dead pump. No power is the relay, the inertia switch, or the CCRM.",
      "Pressure needs a gauge on the rail's Schrader valve. Don't crack a line open because you're curious. Relieve it, rags, glasses.",
      "A pump that runs but the car dies hot can be a pump that's weak under load, or a filter. Check the filter. It's cheaper."
    ],
    keywords: ["fuel pump", "no start", "pressure"]
  },
  {
    id: "fuel-filter",
    name: "Fuel filter",
    system: "fuel",
    stage: 3,
    ex: [-0.22, -0.16, 0],
    circuit: "fuel",
    blurb: "Motorcraft FG-986, on the driver frame rail under the car. It is a maintenance part. A restricted filter is a car that runs, then falls down under load.",
    specs: [{ label: "Part", value: "FG-986" }],
    checks: [
      "Relieve pressure at the rail first. Cracking this filter under pressure sprays fuel on you and the exhaust.",
      "Note the flow arrow. Backwards runs, badly, and then the new pump gets blamed.",
      "The line clips are plastic and one-time if they're brittle. Have clips."
    ],
    keywords: ["fuel filter", "fg-986"]
  },
  {
    id: "fuel-line",
    name: "Fuel line",
    system: "fuel",
    stage: 3,
    ex: [0, -0.2, 0],
    circuit: "fuel",
    blurb: "The steel line from the filter up to the rail. Returnless, so there isn't a second return line like the older cars.",
    checks: [
      "Rust at the filter fittings and along the rail. A pinhole under load is a fire. Don't 'seep and see'.",
      "Nylon lines at the tank hate heat and being bent sharp. Replace a white, chalky line."
    ],
    keywords: ["fuel line"]
  },
  {
    id: "fuel-rail",
    name: "Fuel rail",
    system: "fuel",
    stage: 4,
    parent: "intake-lower",
    ex: [0.14, 0.14, 0],
    circuit: "fuel",
    blurb: "Rail on the lower intake feeding six injectors. There is a Schrader valve for a gauge. Pressure is set in the tank on this returnless car, not by a regulator you can swap on the rail.",
    checks: [
      "Cap the Schrader. A missing cap leaks and looks like an injector.",
      "When the rail comes off, the injector O-rings stay in the head or the cup and then the new ones double up. Look."
    ],
    keywords: ["fuel rail", "schrader", "pressure"]
  },
  {
    id: "injectors",
    name: "Fuel injectors",
    system: "fuel",
    stage: 5,
    parent: "fuel-rail",
    ex: [0, -0.14, 0.1],
    circuit: "fuel",
    blurb: "Six injectors in the lower intake. Sequential fuel. A single-cylinder miss with a good plug, wire, and compression is often this, or the connector.",
    checks: [
      "A noid light or a scope on the connector tells you the PCM is commanding it. Fuel at the rail with no pulse is wiring or the driver. Pulse with no change when you unplug it means the injector is stuck shut.",
      "Don't swap injectors between cylinders without new O-rings. A vacuum leak at the O-ring is a hiss and a trim code on one bank."
    ],
    keywords: ["injector", "misfire"]
  },
  {
    id: "inertia-switch",
    name: "Inertia fuel switch",
    system: "fuel",
    stage: 2,
    ex: [-0.1, 0.22, 0.08],
    circuit: "fuel",
    blurb: "Inertia fuel shutoff, in the trunk on the driver side, ahead of the left tail lamp. A bump, a curb, or a door slam in the right mood pops it. The car then cranks and never starts. You reset it by pushing the button.",
    checks: [
      "First stop on a cranks-but-no-start, before the pump gets replaced. Press the button. If it was up, you found it.",
      "If it pops again on a smooth road, the switch is tired or the car is actually hitting something. Don't bypass it. It's the thing that stops fuel in a wreck.",
      "The trunk location is why people don't find it. It is not under the hood."
    ],
    keywords: ["inertia", "no start", "fuel shutoff", "trunk"]
  },
  {
    id: "battery",
    name: "Battery",
    system: "electrical",
    stage: 3,
    ex: [0.42, 0.32, -0.12],
    circuit: "power",
    blurb: "Motorcraft BXT-59, passenger side of the bay. Group 59 tray. The cables do more no-starts than the battery does, but a battery that is four years old is living on borrowed time.",
    specs: [
      { label: "Part", value: "BXT-59" },
      { label: "Location", value: "Passenger front of the engine bay" }
    ],
    checks: [
      "Load-test it, don't just read 12.4 V and call it good. A surface charge lies.",
      "Clean the posts until they're metal. A green post is resistance, and resistance is a click instead of a crank.",
      "The hold-down exists so the case doesn't crack on the tray. Use it."
    ],
    keywords: ["battery", "bxt-59", "no crank"]
  },
  {
    id: "pdb",
    name: "Power distribution box",
    system: "electrical",
    stage: 3,
    ex: [0.2, 0.36, -0.28],
    circuit: "power",
    blurb: "Under-hood power distribution box on the radiator support, passenger side. Maxi fuses for the alternator, the blower, ABS if you have it, and the feeds into the cabin. The lid has the map. Use the lid, not a guess.",
    checks: [
      "A charging problem with a good alternator is often the big fuse in here, or the nut on the alternator stud.",
      "Water in this box corrodes from the bottom. A wet fuse looks fine and feeds nothing.",
      "Fuses get replaced with the same amp. A 30 where a 10 belongs is how harnesses burn."
    ],
    keywords: ["fuse", "power distribution", "maxi"]
  },
  {
    id: "ccrm",
    name: "CCRM",
    system: "electrical",
    stage: 3,
    ex: [0.28, 0.22, -0.16],
    circuit: "power",
    blurb: "Constant Control Relay Module, up front in the bay. It carries the fuel-pump relay, the PCM power relay, and the A/C clutch relay. A no-pump, no-spark, no-A/C combo is this box more often than three separate failures.",
    checks: [
      "Feel and listen for the pump prime when a helper turns the key. Nothing, and the inertia switch is set, means look here.",
      "The connectors water-wick. Unplug, look for green, and don't force the pins.",
      "It's a module, not a relay you pry open and file. Replace it if the feeds are good and the outputs are dead."
    ],
    keywords: ["ccrm", "relay", "fuel pump relay", "no start"]
  },
  {
    id: "fuse-panel",
    name: "Dash fuse panel",
    system: "electrical",
    stage: 2,
    ex: [-0.48, -0.02, 0.05],
    circuit: "power",
    blurb: "Instrument-panel fuse panel at the driver's left knee. Interior lamps, the radio, wipers, the cluster, and a lot of switched power. The owner's manual has the chart that matches the lid.",
    checks: [
      "A whole group of dead accessories is one fuse in here, not six bad parts.",
      "The panel pulls into the footwell on these cars. Don't break the hinge. And kill the key before you pull a relay with your finger in the socket."
    ],
    keywords: ["fuse panel", "interior fuse"]
  },
  {
    id: "pcm",
    name: "EEC-V PCM",
    system: "electrical",
    stage: 2,
    ex: [0.55, 0.02, 0.06],
    circuit: "sensor",
    blurb: "EEC-V PCM behind the passenger kick panel. It runs fuel, spark, and the gauges' brain. It is not the first part you replace on a no-start. Power, ground, and the crank sensor come first.",
    checks: [
      "A PCM that is wet from a windshield or heater-core leak acts possessed. Dry the kick panel before you buy a computer.",
      "Connectors are lever-locked. Break the lock and you'll never trust the pins again. Release the latch.",
      "Don't flash or 'tune' it to fix a vacuum leak. The fuel trims were already trying to tell you."
    ],
    keywords: ["pcm", "ecu", "eec", "computer"]
  },
  {
    id: "starter-relay",
    name: "Starter relay",
    system: "electrical",
    stage: 3,
    parent: "pdb",
    ex: [0.08, 0.08, -0.06],
    circuit: "start",
    blurb: "Starter relay in the power distribution box. The ignition switch and the clutch switch (or the neutral switch on an automatic) have to agree before this closes.",
    checks: [
      "A single solid click at the relay with no click at the starter is this relay or the cable from here to the starter.",
      "On a manual car, the clutch switch is in series. A switch that never closes looks like a dead relay. Try the pedal all the way down, then check the switch."
    ],
    keywords: ["starter relay", "no crank"]
  },
  {
    id: "ignition-switch",
    name: "Ignition switch",
    system: "electrical",
    stage: 3,
    parent: "column",
    ex: [-0.1, 0.04, 0],
    circuit: "start",
    blurb: "Electrical half of the ignition switch, on the column, not the lock cylinder you put the key in. The cylinder turns the switch. A worn switch drops power to the cluster and the starter at the same time.",
    checks: [
      "Wiggle the key in RUN. A flicker of the cluster is the switch or the cylinder, which wears the switch actuator.",
      "The switch is a plug-in on the column. Don't pull the column apart to get to a part that unclips from the bottom."
    ],
    keywords: ["ignition switch", "no crank", "column"]
  },
  {
    id: "clutch-switch",
    name: "Clutch safety switch",
    system: "electrical",
    stage: 3,
    parent: "pedals",
    ex: [-0.08, 0.06, -0.06],
    circuit: "start",
    blurb: "Switch at the top of the clutch pedal. It must close before the starter relay will. It is also how some of these cars cancel cruise.",
    checks: [
      "If it only starts when you pull the pedal up with your foot, the switch is out of adjustment or the pedal bushings are gone.",
      "Don't bypass it and leave it bypassed. A car that starts in gear will leave through the wall."
    ],
    keywords: ["clutch switch", "neutral safety"]
  },
  {
    id: "brake-switch",
    name: "Brake light switch",
    system: "electrical",
    stage: 3,
    parent: "pedals",
    ex: [0.06, 0.06, -0.05],
    circuit: "lamps",
    blurb: "Switch on the brake pedal. It feeds the tail lamps' brake section and cancels cruise. A low pedal or a switch that's too tight leaves the brake lights on and cooks the sockets.",
    checks: [
      "Have a helper watch the lamps. If they stay on with the pedal up, this switch is adjusted too tight or the pedal isn't returning.",
      "Cruise that won't set is often this switch too. One part, two complaints."
    ],
    keywords: ["brake switch", "cruise"]
  },
  {
    id: "headlamp-switch",
    name: "Headlamp switch",
    system: "electrical",
    stage: 2,
    parent: "dash",
    ex: [-0.2, 0.1, -0.12],
    circuit: "lamps",
    blurb: "Dash headlamp switch. Park, head, and the interior dimmer. The switch gets hot and the plastic browns. That's not normal aging. That's resistance.",
    checks: [
      "A switch that's too hot to touch is done, and the connector behind it is probably browned too. Replace both or the new switch dies.",
      "Dimmer trouble that only affects the cluster is this switch. A dead cluster with no lamps involved is the cluster or its fuse."
    ],
    keywords: ["headlamp switch", "dimmer"]
  },
  {
    id: "dpfe",
    name: "DPFE sensor",
    system: "electrical",
    stage: 3,
    ex: [-0.2, 0.18, -0.12],
    circuit: "sensor",
    blurb: "Delta pressure feedback sensor for the EGR, on the driver side of the bay with two rubber hoses. The hoses rot. The sensor lies. The car surges, stalls coming to a stop, or sets an EGR code.",
    checks: [
      "The hoses are not interchangeable. Mark upstream and downstream before they come off. Or take a picture that is actually in focus.",
      "A cracked hose is the failure more often than the sensor. Replace the hoses when you replace the sensor.",
      "Don't block the EGR to 'test' and then leave it blocked. It overheats the chambers and the PCM will know."
    ],
    keywords: ["dpfe", "egr", "surge", "stall"]
  },
  {
    id: "seat-l",
    name: "Driver seat",
    system: "interior",
    stage: 2,
    ex: [-0.08, 0.7, 0.18],
    blurb: "Driver bucket. The tracks and the rear bolts are what the seat belt is counting on. A seat that rocks is a loose bolt or a torn floor, not 'character'.",
    checks: [
      "Torque the seat bolts. They're structural. A sliding seat in a stop is a bad day.",
      "The power lumbar, if you have it, is a blister and a switch. A dead bladder with the switch clicking is the bladder."
    ],
    keywords: ["seat"]
  },
  {
    id: "seat-r",
    name: "Passenger seat",
    system: "interior",
    stage: 2,
    ex: [0.08, 0.7, 0.18],
    blurb: "Passenger bucket. Same floor bolts. The occupancy sensor, if equipped, lives in the cushion and matters to the airbag light.",
    checks: [
      "An airbag light after seat work is often the connector under this seat, unplugged, not a deployed bag.",
      "Don't mix the left and right tracks. They aren't."
    ],
    keywords: ["seat", "airbag light"]
  },
  {
    id: "dash",
    name: "Instrument panel",
    system: "interior",
    stage: 2,
    ex: [0, 0.32, -0.42],
    blurb: "Dash pad and structure. The cluster, the headlamp switch, and the passenger airbag live here. The heater core is behind it, and that is the job nobody wants.",
    checks: [
      "A sweet smell and a wet passenger carpet is the heater core until a hose at the firewall proves otherwise.",
      "Cracks in the pad are cosmetic. A loose pad that buzzes is a clip or a screw at the cowl, not a bad speaker."
    ],
    keywords: ["dash", "heater"]
  },
  {
    id: "cluster",
    name: "Instrument cluster",
    system: "interior",
    stage: 2,
    parent: "dash",
    ex: [-0.06, 0.14, -0.14],
    circuit: "sensor",
    blurb: "Gauge cluster. Needles fall off, steppers die, and the backlight goes brown. A speedo problem can be the cluster or the VSS. A fuel gauge that lies can be the cluster or the sender in the tank.",
    checks: [
      "If every gauge dies together, look at cluster power and ground before the senders. Senders don't fail as a choir.",
      "The cluster comes out with the bezel. Don't pry the lens. The clips are at the bottom."
    ],
    keywords: ["cluster", "gauge", "speedometer"]
  },
  {
    id: "column",
    name: "Steering column",
    system: "interior",
    stage: 2,
    ex: [-0.22, 0.12, -0.22],
    blurb: "Column, with the lock, the multifunction switch, and the ignition switch. The clock spring for the airbag and the horn is in the wheel.",
    checks: [
      "A horn that works when the wheel is straight and dies when it's turned is the clock spring. So is an airbag light that showed up after a wheel was swapped.",
      "Don't spin the wheel with the column disconnected and the battery in. Center the clock spring the way the manual says."
    ],
    keywords: ["column", "clock spring", "horn"]
  },
  {
    id: "steer-wheel",
    name: "Steering wheel",
    system: "interior",
    stage: 2,
    parent: "column",
    ex: [-0.12, 0.04, -0.1],
    blurb: "Wheel and the driver airbag. The airbag is not a horn button you pry off with a screwdriver while the battery is connected.",
    checks: [
      "Disconnect the battery and wait before the airbag comes off. The manual's wait is there because the backup power is real.",
      "The puller holes for the wheel are threaded. Use them. A jaw puller on the plastic is how the wheel becomes two pieces."
    ],
    keywords: ["steering wheel", "airbag"]
  },
  {
    id: "shifter",
    name: "Shifter",
    system: "interior",
    stage: 2,
    ex: [0, 0.4, 0.12],
    blurb: "Floor shifter. On the T-5 the handle, the cup, and the bushing are the slop. On the 4R70W the cable and the neutral safety switch at the lever matter.",
    checks: [
      "T-5: massive play in neutral with the trans quiet is the bushing. Replace it before you rebuild a gearbox that shifts fine from underneath.",
      "Automatic: a car that won't start in Park but starts in Neutral has the shift cable or the switch out of adjustment. Don't bypass the switch."
    ],
    keywords: ["shifter", "bushing"]
  },
  {
    id: "console",
    name: "Console",
    system: "interior",
    stage: 2,
    ex: [0, 0.46, 0.16],
    blurb: "Center console over the shifter. The boot, the power point, and a handful of screws.",
    checks: [
      "A rattle in the console is a coin or a loose screw, found by a light, not by a new interior.",
      "The boot keeps water out of the trans. A torn boot is a repair, not a style."
    ],
    keywords: ["console"]
  },
  {
    id: "pedals",
    name: "Pedal box",
    system: "interior",
    stage: 2,
    ex: [-0.18, 0.08, -0.2],
    blurb: "Clutch, brake, and throttle pedals. The clutch is a cable. The brake pushes a vacuum booster. The throttle is a cable.",
    checks: [
      "A soft brake pedal that does not firm up with the engine off is fluid or a master. A pedal that sinks only with the engine running can be the booster.",
      "Clutch pedal bushings oval out and then the safety switch can't see the pedal. The car no-cranks and the clutch still works."
    ],
    keywords: ["pedal", "booster", "clutch pedal"]
  },
  {
    id: "heater-core",
    name: "Heater core",
    system: "cooling",
    stage: 3,
    parent: "dash",
    ex: [0.36, -0.08, 0.18],
    blurb: "Heater core behind the dash on the passenger side. Sweet smell, fogged glass with a film you can wipe, wet passenger carpet. The hoses at the firewall are the easy version of the same symptom.",
    checks: [
      "Feel both heater hoses at the firewall, engine warm, heat on. Both hot means the core is getting flow. One hot means a plugged core or a closed valve.",
      "Bypass the core with a splice as a test if you must drive it. Don't leave the carpet wet. It rots the floor you're standing on.",
      "The real replacement is a dash-out or a careful cut, depending how the job is done. Budget time. It is not an hour."
    ],
    keywords: ["heater core", "sweet smell", "wet carpet"]
  },
  {
    id: "cable-pos",
    name: "Positive cable",
    system: "electrical",
    stage: 3,
    ex: [0.1, 0.16, -0.12],
    circuit: "power",
    blurb: "Battery positive to the power distribution box and the alternator B+ stud. Fat cable, red. Corrosion under the insulation, an inch from the lug, is the classic hidden resistance.",
    checks: [
      "Voltage drop from the battery post to the alternator stud, engine running. More than a few tenths means this cable or a fuse, not a bad alternator.",
      "Don't hammer a lug tighter to fix a green cable. Cut it back to bright copper or replace it."
    ],
    keywords: ["positive cable", "voltage drop"]
  },
  {
    id: "cable-start",
    name: "Starter cable",
    system: "electrical",
    stage: 3,
    ex: [0.08, -0.1, -0.08],
    circuit: "start",
    blurb: "The heavy feed from the power box / solenoid circuit down to the starter stud.",
    checks: [
      "Crank and measure at the starter stud. If the battery stays at 11 V and the stud falls to 8, this cable or the connection is the problem.",
      "The stud nut is small. It strips. Then the starter 'fails' every summer."
    ],
    keywords: ["starter cable"]
  },
  {
    id: "cable-neg",
    name: "Negative cable",
    system: "electrical",
    stage: 3,
    ex: [0.05, 0.08, -0.1],
    circuit: "ground",
    blurb: "Battery negative to the body and on to the engine. A bad ground here is a no-crank, a dim-everything, and a alternator that won't charge, all at once.",
    checks: [
      "Voltage drop from the battery negative post to the engine block, while cranking. It should be almost nothing. If the block is half a volt above the post, the ground is the job.",
      "A paint-covered ground eye is not a ground. Clean to metal."
    ],
    keywords: ["ground", "negative cable"]
  },
  {
    id: "ground-engine",
    name: "Engine ground strap",
    system: "electrical",
    stage: 4,
    parent: "engine-block",
    ex: [-0.12, 0.05, 0.1],
    circuit: "ground",
    blurb: "Strap from the block or the head to the body. The starter and the ignition both need it. A car that cranks slow and has weird sensor codes can be this one strap.",
    checks: [
      "Tug it. A strap that looks connected and is held by one strand is open.",
      "After paint or powdercoat on a swapped part, this eye is sitting on insulation. Scrape it."
    ],
    keywords: ["ground strap"]
  },
  {
    id: "harness-pcm",
    name: "PCM power feed",
    system: "electrical",
    stage: 3,
    ex: [0.12, 0.08, -0.06],
    circuit: "power",
    blurb: "Power from the CCRM and the power box into the PCM. No power here, no fuel pulse, no spark command.",
    checks: [
      "Check power and ground at the PCM connector with a real back-probe, not a nail through the wire.",
      "A blown PCM relay feed is a no-start that still cranks. Don't buy a pump for it."
    ],
    keywords: ["pcm power"]
  },
  {
    id: "harness-fuel",
    name: "Fuel pump harness",
    system: "electrical",
    stage: 3,
    ex: [0, -0.12, 0],
    circuit: "fuel",
    blurb: "The run from the CCRM, back along the driver side, through the inertia switch in the trunk, down to the pump. That is the whole no-start story on a lot of these cars.",
    checks: [
      "Find 12 V at the inertia switch when the key is on and the pump should be priming. Power in, nothing out, means the switch is open.",
      "Chafing along the rocker is a pump that works until the suspension loads. Look at the loom, don't just throw a pump at it."
    ],
    keywords: ["fuel pump harness", "inertia"]
  },
  {
    id: "harness-edis",
    name: "EDIS harness",
    system: "electrical",
    stage: 4,
    parent: "engine-block",
    ex: [0.06, 0.1, -0.08],
    circuit: "ignition",
    blurb: "The crank-sensor and coil-pack branch of the engine harness. Spark command lives in this loom.",
    checks: [
      "Oil in the connector at the crank sensor is the usual find. Dielectric grease after it's clean and dry.",
      "A rubbed-through wire at the valve cover bracket kills one coil circuit and two cylinders."
    ],
    keywords: ["edis", "coil harness"]
  },
  {
    id: "plug-wires",
    name: "Plug wires",
    system: "electrical",
    stage: 5,
    parent: "coil-pack",
    ex: [0, 0.16, 0.04],
    circuit: "ignition",
    blurb: "Six wires from the coil pack to the plugs. They are numbered. Waste-spark means each tower feeds a pair. Oil from the valve covers kills them in pairs of boots.",
    checks: [
      "A wire that tracks (white line burned into the boot) is done. Replace the set if two are bad. The others are the same age.",
      "Seat the boot until it clicks. A loose boot is a miss under load only, which is maddening and cheap.",
      "Route them in the looms. A wire against the manifold melts and then the coil gets blamed."
    ],
    keywords: ["plug wires", "boots"]
  },
  {
    id: "harness-inj",
    name: "Injector harness",
    system: "electrical",
    stage: 4,
    parent: "intake-lower",
    ex: [0.08, 0.1, 0],
    circuit: "fuel",
    blurb: "The injector branch from the PCM to the rail. Sequential, so each injector has its own driver wire and a shared power.",
    checks: [
      "A single dead injector with the others fine is often the clip, which gets brittle and backs off.",
      "Shared power dead means no injector fires. That's a fuse or a relay, not six bad injectors."
    ],
    keywords: ["injector harness"]
  },
  {
    id: "harness-sensors",
    name: "Sensor harness",
    system: "electrical",
    stage: 4,
    parent: "engine-block",
    ex: [0.04, 0.08, -0.04],
    circuit: "sensor",
    blurb: "The engine-sensor branch: MAF, TPS, ECT, IAC, both O2 sensors, DPFE, VSS. One chafed spot explains a cluster of 'unrelated' codes.",
    checks: [
      "Look at where it passes the valve cover bolts and the exhaust. Heat and a sharp edge are the whole failure mode.",
      "Repair with solder and glue-lined heat shrink, not a Scotch lock. A Scotch lock is a future no-start."
    ],
    keywords: ["harness", "sensor"]
  },
  {
    id: "harness-start",
    name: "Start control",
    system: "electrical",
    stage: 3,
    ex: [-0.08, 0.04, -0.08],
    circuit: "start",
    blurb: "The small wire from the ignition switch, through the clutch switch, to the starter relay. This is control, not the fat cable that actually spins the starter.",
    checks: [
      "If the relay never clicks and the bulb in a test light at the small terminal stays dark while the key is in START, this circuit is open. The clutch switch is the usual open."
    ],
    keywords: ["start wire", "clutch switch"]
  },
  {
    id: "harness-lamps",
    name: "Front lamp harness",
    system: "electrical",
    stage: 2,
    ex: [0, 0.08, -0.16],
    circuit: "lamps",
    blurb: "From the dash switch and the fuse panel out to both headlamps. The multifunction switch on the column does the high beams and the turns.",
    checks: [
      "One dim headlamp is the ground at that lamp. Both dim is the switch or the ground at the radiator support.",
      "The column switch fails and then the highs stick or the turns die on one side. It's a switch, not the flasher, if the hazard still works."
    ],
    keywords: ["headlamp harness", "multifunction"]
  },
  {
    id: "harness-tails",
    name: "Rear lamp harness",
    system: "electrical",
    stage: 2,
    ex: [0, 0.06, 0.2],
    circuit: "lamps",
    blurb: "From the brake switch and the fuse panel back to the tri-bar lamps. It runs the rockers. A crushed harness under a rocker trim screw kills one tail and not the other.",
    checks: [
      "Check the socket before the harness. Melted sockets are common and they look like a wiring problem from the driver's seat.",
      "A trailer hitch someone wired with scotch locks lives in this circuit. Look for it."
    ],
    keywords: ["tail harness", "brake lights"]
  },
  {
    id: "pigtail-cluster",
    name: "Cluster harness",
    system: "electrical",
    stage: 2,
    parent: "dash",
    ex: [-0.05, 0.08, -0.08],
    circuit: "sensor",
    blurb: "The plug into the back of the cluster. A gauge that drops out when you tap the top of the dash is this connector or a cracked solder joint, which these clusters are famous for.",
    checks: [
      "Reseat it before you buy a cluster. Then, if the solder is cracked, that's a cluster repair, not a new PCM."
    ],
    keywords: ["cluster plug"]
  }
]);
var PART_LIST = Object.values(PARTS);
function partView(id, trans) {
  const part = PARTS[id];
  if (!part) {
    return {
      id,
      name: "Unknown",
      system: "chassis",
      stage: 0,
      ex: [0, 0, 0],
      blurb: "",
      specs: [],
      fasteners: [],
      checks: [],
      keywords: []
    };
  }
  if (part.alt && part.alt.when === trans) {
    return {
      ...part,
      name: part.alt.name,
      blurb: part.alt.blurb,
      specs: part.alt.specs,
      checks: part.alt.checks
    };
  }
  return part;
}
function searchParts(q) {
  const query = q.trim().toLowerCase();
  if (!query) return [];
  const terms = query.split(/\s+/);
  return PART_LIST.filter((part) => {
    const hay = [
      part.name,
      part.blurb,
      part.system,
      part.alt?.name ?? "",
      part.alt?.blurb ?? "",
      ...part.keywords,
      ...part.specs.flatMap((s) => [s.label, s.value]),
      ...part.fasteners.flatMap((f) => [f.name, f.thread, f.torque ?? ""]),
      ...part.checks
    ].join(" ").toLowerCase();
    return terms.every((term) => hay.includes(term));
  }).slice(0, 8);
}

// lib/mustang/live.ts
var live = {
  stage: 0,
  targetStage: 0,
  dolly: null,
  focusing: false,
  focusId: null,
  recenter: false,
  menuFromPart: false
};
function clamp(n, a, b) {
  return Math.max(a, Math.min(b, n));
}
function openAmount(stage, partStage) {
  if (partStage <= 0) return 0;
  return clamp(stage - (partStage - 1), 0, 1);
}
function explodeOf(id, stage) {
  let x = 0;
  let y = 0;
  let z = 0;
  let cur = id;
  const seen = /* @__PURE__ */ new Set();
  while (cur && !seen.has(cur)) {
    seen.add(cur);
    const part = PARTS[cur];
    if (!part) break;
    const a = openAmount(stage, part.stage) * 2.25;
    x += part.ex[0] * a;
    y += part.ex[1] * a;
    z += part.ex[2] * a;
    cur = part.parent;
  }
  return [x, y, z];
}

// node_modules/zustand/esm/vanilla.mjs
var createStoreImpl = (createState) => {
  let state;
  const listeners = /* @__PURE__ */ new Set();
  const setState = (partial, replace) => {
    const nextState = typeof partial === "function" ? partial(state) : partial;
    if (!Object.is(nextState, state)) {
      const previousState = state;
      state = (replace != null ? replace : typeof nextState !== "object" || nextState === null) ? nextState : Object.assign({}, state, nextState);
      listeners.forEach((listener) => listener(state, previousState));
    }
  };
  const getState = () => state;
  const getInitialState = () => initialState;
  const subscribe = (listener) => {
    listeners.add(listener);
    return () => listeners.delete(listener);
  };
  const api = { setState, getState, getInitialState, subscribe };
  const initialState = state = createState(setState, getState, api);
  return api;
};
var createStore = ((createState) => createState ? createStoreImpl(createState) : createStoreImpl);

// node_modules/zustand/esm/react.mjs
var import_react = __toESM(require_react(), 1);
var identity = (arg) => arg;
function useStore(api, selector = identity) {
  const slice = import_react.default.useSyncExternalStore(
    api.subscribe,
    import_react.default.useCallback(() => selector(api.getState()), [api, selector]),
    () => selector(api.getInitialState())
  );
  import_react.default.useDebugValue(slice);
  return slice;
}
var createImpl = (createState) => {
  const api = createStore(createState);
  const useBoundStore = (selector) => useStore(api, selector);
  Object.assign(useBoundStore, api);
  return useBoundStore;
};
var create = ((createState) => createState ? createImpl(createState) : createImpl);

// lib/mustang/diagram.ts
var NODES = [
  { id: "battery", x: 16, y: 28, w: 132, h: 48, label: "Battery", sub: "BXT-59" },
  { id: "cable-neg", x: 16, y: 92, w: 132, h: 40, label: "Negative", sub: "Body ground" },
  { id: "ignition-switch", x: 16, y: 168, w: 132, h: 44, label: "Ignition switch", sub: "Column" },
  { id: "clutch-switch", x: 16, y: 224, w: 132, h: 44, label: "Clutch switch", sub: "Pedal" },
  { id: "fuse-panel", x: 16, y: 292, w: 132, h: 44, label: "Dash fuses", sub: "Left knee" },
  { id: "headlamp-switch", x: 16, y: 352, w: 132, h: 44, label: "Lamp switch", sub: "Dash" },
  { id: "brake-switch", x: 16, y: 412, w: 132, h: 44, label: "Brake switch", sub: "Pedal" },
  { id: "pdb", x: 196, y: 28, w: 140, h: 48, label: "Power box", sub: "Radiator support" },
  { id: "starter-relay", x: 196, y: 92, w: 140, h: 40, label: "Starter relay", sub: "In the power box" },
  { id: "ccrm", x: 196, y: 156, w: 140, h: 48, label: "CCRM", sub: "Pump & PCM relays" },
  { id: "pcm", x: 196, y: 228, w: 140, h: 56, label: "PCM", sub: "EEC-V, kick panel" },
  { id: "dpfe", x: 196, y: 304, w: 140, h: 40, label: "DPFE", sub: "EGR hoses" },
  { id: "maf", x: 196, y: 360, w: 140, h: 40, label: "MAF", sub: "Air duct" },
  { id: "tps", x: 196, y: 412, w: 140, h: 36, label: "TPS", sub: "Throttle" },
  { id: "ect", x: 196, y: 458, w: 140, h: 36, label: "ECT", sub: "Coolant" },
  { id: "alternator", x: 392, y: 28, w: 136, h: 44, label: "Alternator", sub: "B+ stud" },
  { id: "starter", x: 392, y: 88, w: 136, h: 44, label: "Starter", sub: "Passenger block" },
  { id: "ckp", x: 392, y: 148, w: 136, h: 40, label: "Crank sensor", sub: "Front cover" },
  { id: "coil-pack", x: 392, y: 204, w: 136, h: 44, label: "Coil pack", sub: "EDIS" },
  { id: "inertia-switch", x: 392, y: 268, w: 136, h: 48, label: "Inertia switch", sub: "Trunk, driver" },
  { id: "fuel-rail", x: 392, y: 332, w: 136, h: 40, label: "Fuel rail", sub: "Schrader" },
  { id: "o2-up", x: 392, y: 388, w: 136, h: 36, label: "O2 upstream", sub: "M18\xD71.5" },
  { id: "o2-down", x: 392, y: 434, w: 136, h: 36, label: "O2 downstream", sub: "After the cat" },
  { id: "fuel-pump", x: 584, y: 268, w: 140, h: 48, label: "Fuel pump", sub: "In the tank" },
  { id: "plugs-r", x: 584, y: 188, w: 140, h: 40, label: "Plugs 1-2-3", sub: "Passenger bank" },
  { id: "plugs-l", x: 584, y: 140, w: 140, h: 40, label: "Plugs 4-5-6", sub: "Driver bank" },
  { id: "injectors", x: 584, y: 332, w: 140, h: 40, label: "Injectors", sub: "Six, sequential" },
  { id: "iac", x: 584, y: 388, w: 140, h: 36, label: "IAC", sub: "Idle air" },
  { id: "vss", x: 584, y: 434, w: 140, h: 36, label: "VSS", sub: "Tailshaft" },
  { id: "headlamp-l", x: 584, y: 28, w: 140, h: 36, label: "Headlamp L", sub: "Driver" },
  { id: "headlamp-r", x: 740, y: 28, w: 120, h: 36, label: "Headlamp R", sub: "Passenger" },
  { id: "taillamp-l", x: 584, y: 78, w: 140, h: 36, label: "Tail lamp L", sub: "Tri-bar" },
  { id: "taillamp-r", x: 740, y: 78, w: 120, h: 36, label: "Tail lamp R", sub: "Tri-bar" },
  { id: "cluster", x: 740, y: 228, w: 120, h: 44, label: "Cluster", sub: "Gauges" }
];
var WIRES = [
  {
    id: "cable-pos",
    circuit: "power",
    ends: ["battery", "pdb", "alternator"],
    routes: [
      [
        [148, 52],
        [196, 52]
      ],
      [
        [336, 52],
        [392, 50]
      ]
    ]
  },
  {
    id: "cable-start",
    circuit: "start",
    ends: ["pdb", "starter-relay", "starter"],
    routes: [
      [
        [266, 76],
        [266, 92]
      ],
      [
        [336, 112],
        [392, 110]
      ]
    ]
  },
  {
    id: "cable-neg",
    circuit: "ground",
    ends: ["battery", "ground-engine"],
    routes: [
      [
        [82, 76],
        [82, 92]
      ]
    ]
  },
  {
    id: "harness-pcm",
    circuit: "power",
    ends: ["ccrm", "pcm"],
    routes: [
      [
        [266, 204],
        [266, 228]
      ]
    ]
  },
  {
    id: "harness-fuel",
    circuit: "fuel",
    ends: ["ccrm", "inertia-switch", "fuel-pump"],
    routes: [
      [
        [336, 180],
        [392, 292]
      ],
      [
        [528, 292],
        [584, 292]
      ]
    ]
  },
  {
    id: "harness-edis",
    circuit: "ignition",
    ends: ["pcm", "ckp", "coil-pack"],
    routes: [
      [
        [336, 256],
        [364, 256],
        [364, 168],
        [392, 168]
      ],
      [
        [364, 226],
        [392, 226]
      ]
    ]
  },
  {
    id: "plug-wires",
    circuit: "ignition",
    ends: ["coil-pack", "plugs-l", "plugs-r"],
    routes: [
      [
        [528, 220],
        [556, 220],
        [556, 160],
        [584, 160]
      ],
      [
        [556, 208],
        [584, 208]
      ]
    ]
  },
  {
    id: "harness-inj",
    circuit: "fuel",
    ends: ["pcm", "fuel-rail", "injectors"],
    routes: [
      [
        [336, 270],
        [392, 352]
      ],
      [
        [528, 352],
        [584, 352]
      ]
    ]
  },
  {
    id: "harness-sensors",
    circuit: "sensor",
    ends: ["pcm", "maf", "tps", "ect", "iac", "o2-up", "o2-down", "dpfe", "vss"],
    routes: [
      [
        [266, 284],
        [266, 304]
      ],
      [
        [236, 284],
        [196, 380]
      ],
      [
        [250, 300],
        [196, 430]
      ],
      [
        [250, 300],
        [196, 476]
      ],
      [
        [336, 270],
        [520, 406],
        [584, 406]
      ],
      [
        [336, 256],
        [392, 406]
      ],
      [
        [392, 452],
        [470, 452]
      ],
      [
        [336, 270],
        [520, 452],
        [584, 452]
      ]
    ]
  },
  {
    id: "harness-start",
    circuit: "start",
    ends: ["ignition-switch", "clutch-switch", "starter-relay"],
    routes: [
      [
        [148, 190],
        [172, 190],
        [172, 246],
        [148, 246]
      ],
      [
        [172, 190],
        [196, 112]
      ]
    ]
  },
  {
    id: "harness-lamps",
    circuit: "lamps",
    ends: ["headlamp-switch", "fuse-panel", "headlamp-l", "headlamp-r"],
    routes: [
      [
        [82, 336],
        [82, 352]
      ],
      [
        [148, 374],
        [760, 374],
        [760, 64],
        [654, 46]
      ],
      [
        [760, 46],
        [740, 46]
      ]
    ]
  },
  {
    id: "harness-tails",
    circuit: "lamps",
    ends: ["brake-switch", "taillamp-l", "taillamp-r"],
    routes: [
      [
        [148, 434],
        [760, 434],
        [760, 114],
        [654, 96]
      ],
      [
        [760, 96],
        [740, 96]
      ]
    ]
  },
  {
    id: "pigtail-cluster",
    circuit: "sensor",
    ends: ["fuse-panel", "cluster"],
    routes: [
      [
        [148, 314],
        [800, 314],
        [800, 272]
      ]
    ]
  },
  {
    id: "fuel-line",
    circuit: "fuel",
    ends: ["fuel-pump", "fuel-filter", "fuel-rail"],
    routes: [
      [
        [654, 316],
        [654, 332],
        [528, 352]
      ]
    ]
  }
];
var WIRE_BY_ID = new Map(WIRES.map((w) => [w.id, w]));
function traceOf(id) {
  if (!id) return [];
  const hit = /* @__PURE__ */ new Set([id]);
  const wire = WIRE_BY_ID.get(id);
  if (wire) {
    for (const end of wire.ends) hit.add(end);
    return [...hit];
  }
  for (const item of WIRES) {
    if (item.ends.includes(id)) hit.add(item.id);
  }
  return [...hit];
}

// lib/mustang/flows.ts
var FUEL_PUMP_POWER = {
  id: "fuel-pump-power",
  title: "Fuel pump power",
  lead: "Cranks and will not fire, or you never hear the pump. This path is battery, the under-hood fuse, the CCRM relay, the inertia switch in the driver-side trunk, then the connector on the tank. This car has no fuel-pump driver module. Do not drop the tank until a step says the pump itself is dead.",
  circuit: "fuel",
  steps: [
    {
      id: "prime",
      partId: "fuel-pump",
      title: "Listen for the prime",
      where: "At the filler, cap off, or with an ear at the trunk floor.",
      harness: "Not yet. This step is only the sound.",
      wires: [],
      action: "Key to ON. Do not crank. A good circuit runs the pump for about one second, then stops. It runs again while a helper cranks, because the PCM only holds the relay closed once it sees the crank signal.",
      pass: "You heard it. Power is reaching the pump for the prime. If it still will not start, the miss is spark, pressure, or a pump that quits under load. Say so in the note before you buy parts.",
      fail: "Silence. Do not buy a pump. The next stop is the inertia switch, and it is free."
    },
    {
      id: "inertia",
      partId: "inertia-switch",
      title: "Reset the inertia switch",
      where: "Driver side of the trunk, behind the liner, ahead of the left tail lamp. It is not in the passenger kick panel.",
      harness: "Fuel-pump harness in the trunk. Two wires on the switch. The sender wires are not on this switch.",
      wires: [
        {
          role: "Power in, from the CCRM",
          color: "Dark green / yellow"
        },
        {
          role: "Power out, toward the tank",
          color: "Read it on your connector and write it in the note. The feed into the switch is dark green/yellow. The wire leaving it is not the same in every book, so the color on the car wins."
        }
      ],
      action: "Press the reset button until it stays down. Key ON again and listen. A bump, a curb, or a hard slam pops this and the car cranks forever.",
      pass: "The button was up, and now the pump primes. That was the whole job. If it pops again on a smooth road, replace the switch. Do not bypass it.",
      fail: "The button was already down and the pump is still silent. Leave the switch reset and move to the fuse."
    },
    {
      id: "fuse",
      partId: "pdb",
      title: "Fuel-pump fuse",
      where: "Under-hood power distribution box, passenger side of the radiator support. The lid has the map. Use the lid, not a remembered slot.",
      harness: "Battery junction box. The fuse feeds the CCRM. It is not the dash fuse panel at the left knee.",
      wires: [],
      action: "Key off. Pull the fuel-pump fuse printed on the lid. Look at the element against the light. Reseat it, or replace it with the same amp rating that is printed.",
      pass: "It was open, and a new fuse of the same amp makes the pump prime. If the new one blows, find the short before you leave. A bigger fuse burns the harness.",
      fail: "The element is intact. Power is not dying in this fuse. Next is the CCRM."
    },
    {
      id: "ccrm-out",
      partId: "ccrm",
      title: "Relay output",
      where: "CCRM, passenger side of the bay on the radiator support. Black module. The fuel-pump relay is inside it. You do not pry it open.",
      harness: "Engine harness at the CCRM connector.",
      wires: [
        {
          role: "Relay output, runs back to the inertia switch",
          color: "Dark green / yellow"
        },
        {
          role: "Battery feed into the fuel-pump relay",
          color: "Light blue / orange on the 99\u201304 CCRM. Confirm the stripe on your connector before you load it."
        }
      ],
      action: "Backprobe the dark green/yellow. Black lead on battery negative. Key ON. You want battery voltage for about one second, then it falls away. Have a helper crank. It should come back while the engine is turning.",
      pass: "That pulse is there. The relay closed and the PCM commanded it. The open is downstream: the switch, the wire to the tank, the pump, or the ground.",
      fail: "It never goes hot, not even for the one-second prime. Stay at the CCRM. Do not drop the tank."
    },
    {
      id: "relay",
      partId: "ccrm",
      title: "Feed and the click",
      where: "Same CCRM connector.",
      harness: "Engine harness. The PCM grounds the relay coil. That control wire\u2019s color belongs to the EVTM. Do not guess a pin and ground it.",
      wires: [
        {
          role: "Battery feed",
          color: "Light blue / orange. Hot with the key off. It does not wait for the PCM."
        }
      ],
      action: "Key off, then ON, and listen for a click at the CCRM. Meter the light blue/orange to battery negative. It should be battery voltage whether or not the relay clicks.",
      pass: "The feed is hot and you hear the click, but the dark green/yellow stayed dead on the last step. The contacts are open. The CCRM is the failed part, not the pump.",
      fail: "No click, or the light blue/orange is dead. Dead feed: back to the fuse and the wire into the CCRM. Feed is hot and there is no click: the PCM is not grounding the coil, or the coil is open. Still not a pump."
    },
    {
      id: "both-sides",
      partId: "inertia-switch",
      title: "Both sides of the switch",
      where: "Inertia switch connector, driver side of the trunk.",
      harness: "Trunk harness. Unplug it only if you cannot backprobe. The pins are small.",
      wires: [
        { role: "In from the CCRM", color: "Dark green / yellow" },
        {
          role: "Out to the tank",
          color: "Whatever color you wrote down. Both wires should be hot during the prime if the switch is closed."
        }
      ],
      action: "Helper turns the key to ON. During that one second, both wires at the switch should show battery voltage against battery negative. Miss the second and you will call a good switch bad. Do it twice.",
      pass: "Both sides go hot. Power is through the switch. The loss is between here and the pump, or it is the pump, or it is the ground.",
      fail: "Only the dark green/yellow goes hot. The switch is open even though the button looks down. Replace the switch. If neither side goes hot, you missed the prime or the CCRM output was never there. Recheck that step with the helper before you condemn the switch."
    },
    {
      id: "hat",
      partId: "fuel-pump",
      title: "Voltage at the pump connector",
      where: "Top of the tank. Fold the rear seat, pull the trunk carpet, four bolts on the access cover. You can unplug the hat without dropping the tank.",
      harness: "Rear harness at the pump and sender connector. The pump uses two of the pins. The sender uses the others. Do not load-test the sender.",
      wires: [
        {
          role: "Pump power",
          color: "The same wire that was hot on the output side of the inertia switch. Follow that color. Do not stab a sender wire because it is easier to reach."
        },
        {
          role: "Pump ground",
          color: "Black, to the body near the tank. Prove it ohms to battery negative. The sender has its own ground and it will lie to you."
        }
      ],
      action: "During the prime, or while cranking, meter from the pump power pin to the pump ground pin. Write the number down, and write the battery voltage next to it.",
      pass: "Battery voltage, and within about half a volt of the battery. If the pump is silent with that, the last step is the ground drop. A good ground plus this reading is a dead pump.",
      fail: "Zero volts here, but both sides of the inertia switch were hot. The break is the wire between the trunk switch and this connector. A reading several volts under the battery is a drop in a connector, not a weak pump."
    },
    {
      id: "ground",
      partId: "fuel-pump",
      title: "Ground drop",
      where: "Pump ground pin, and the ground eye on the body near the tank.",
      harness: "The black ground in the tank harness. Clean the eye if it is green. Do not add a new ground to a painted stud and call it done.",
      wires: [{ role: "Pump ground", color: "Black" }],
      action: "Key off. Ohms from the ground pin to battery negative. Then, during the prime, volts from that same pin to battery negative. A good ground is near 0 ohms and under about 0.2 V while the pump is commanded.",
      pass: "Ground is clean, and the last step had battery voltage at the pump, and it never ran. The pump is the failed part. Then you drop the tank. Replace the sock with it.",
      fail: "High ohms, or the pin rises off battery negative while the pump is commanded. Fix the ground before you buy a pump. A pump on a bad ground gets returned as defective."
    }
  ]
};
var EVAP = {
  id: "evap",
  title: "Tank vapor valve",
  lead: "The valve that regulates evaporation is the EVAP purge valve, in the right front inner fender behind the splash shield. It is normally closed. The PCM duty-cycles it and intake vacuum pulls vapor out of the canister. It is not the fuel-pressure regulator. This 3.8 is returnless. Fuel pressure is set in the tank.",
  circuit: "all",
  steps: [
    {
      id: "purge",
      partId: "evap-purge",
      title: "Purge valve",
      where: "Right front inner fender, behind the splash shield. Right wheel and the shield come off to reach it.",
      harness: "Engine harness. Two-wire solenoid. One side is power, the other is the PCM driver.",
      wires: [
        {
          role: "Power and PCM driver",
          color: "Confirm both colors in the 2001 EVTM before you pierce either wire. The test that matters is duty cycle, not a guessed stripe."
        }
      ],
      action: "Key on, engine running after it is warm. A scan tool should show the PCM commanding purge. Unplug the valve at idle. A valve stuck open changes the idle the moment you unplug it. A valve that never clicks and never gets commanded stores vapor until a hose or the cap burps an evap code.",
      pass: "It clicks when commanded, the idle changes when you unplug a valve that was open, and the hoses hold vacuum on the intake side. The valve is doing its job.",
      fail: "Stuck open is a vacuum leak. Never opens, with power and a command present, is a bad valve. No command is the PCM input side, not a reason to replace the canister yet."
    },
    {
      id: "vent",
      partId: "evap-vent",
      title: "Vent solenoid",
      where: "On the canister, left rear quarter. Normally open so the canister can breathe. The PCM closes it only to seal the system for the leak test.",
      harness: "Rear harness at the canister. Separate connector from the purge valve up front.",
      wires: [
        {
          role: "Power and PCM driver",
          color: "Read them on the connector. Do not copy the purge-valve colors. It is a different circuit."
        }
      ],
      action: "With the connector off, the vent path through the solenoid should be open. You can blow through it. Commanded closed, during a leak test, it should shut. A vent that is stuck closed pressure-locks the tank. A vent that will not close fails the leak test and sets an evap code with a good cap.",
      pass: "Open at rest, closes when commanded, hoses seated and not cracked.",
      fail: "Stuck shut: tank pressure and a hard-to-open cap. Stuck open during the test: the leak the PCM sees may be this solenoid, not a hole in the tank."
    },
    {
      id: "tube",
      partId: "vapor-valve",
      title: "Vapor valve on the tank",
      where: "On top of the tank. Ford services the vapor control valve, the vapor vent valve, and the inline tank-pressure sensor as one tube assembly.",
      harness: "The pressure sensor has its own connector on that tube. The valves themselves are not a solenoid you can duty-cycle.",
      wires: [
        {
          role: "Tank pressure sensor",
          color: "Reference, signal, and return. Confirm the three colors in the EVTM. A wrong backprobe on the signal wire sets a false leak code."
        }
      ],
      action: "Do not crack these hoses with the tank full and hot. Mark every hose. A liquid-filled line into the canister means this valve is letting fuel over, not just vapor. The sensor should move when you open the cap and the tank pressure equalizes.",
      pass: "Hoses are dry of liquid fuel, the sensor reads a change when the cap comes off, and the tube is not cracked at the tank nipple.",
      fail: "Liquid in the vapor hose, or a sensor that stays pegged with the cap off. The tube assembly is the service part. The purge valve up front will not fix that."
    }
  ]
};
function flowById(id) {
  if (!id) return null;
  if (id === FUEL_PUMP_POWER.id) return FUEL_PUMP_POWER;
  if (id === EVAP.id) return EVAP;
  if (id.startsWith("part:")) return generic(id.slice(5));
  return null;
}
function flowForPart(partId) {
  if (partId === "fuel-pump" || partId === "inertia-switch" || partId === "ccrm" || partId === "pdb") {
    return FUEL_PUMP_POWER;
  }
  if (partId === "evap-purge" || partId === "evap-vent" || partId === "vapor-valve" || partId === "tank-pressure" || partId === "evap-canister") {
    return EVAP;
  }
  return generic(partId);
}
function generic(partId) {
  const part = PARTS[partId];
  const checks = part?.checks?.length ? part.checks : ["Look at the part, the connector, and the fastener before you replace it."];
  return {
    id: `part:${partId}`,
    title: part?.name ?? "This part",
    lead: part?.blurb ?? "No catalog note on this part yet.",
    circuit: part?.circuit ?? "all",
    steps: checks.map((check, index) => ({
      id: `${partId}-${index}`,
      partId,
      title: `Check ${index + 1}`,
      where: part?.name ?? "On the car",
      harness: part?.circuit ? "Use the sheet to see which run this part sits on. Confirm the wire color in the EVTM before you pierce it." : "No dedicated circuit on the sheet.",
      wires: [],
      action: check,
      pass: "This check is good. Go to the next one.",
      fail: "This check failed. Stop and write down what you measured. Ask Grok with that note before you buy the part."
    }))
  };
}
function verdict(flow, marks) {
  const answered = flow.steps.filter((step) => marks[step.id]);
  if (!answered.length) return null;
  if (flow.id === "fuel-pump-power") return fuelVerdict(marks);
  const failed = flow.steps.find((step) => marks[step.id] === "fail");
  if (failed) return failed.fail;
  if (flow.steps.every((step) => marks[step.id] === "pass")) return "Every check passed. If the complaint is still there, it is upstream of this part. Ask Grok with the readings you wrote down.";
  return null;
}
function fuelVerdict(marks) {
  if (marks.inertia === "pass") return "The inertia switch was open. The pump should prime now. Leave the button down. If it pops again with no impact, replace the switch. Do not jumper it.";
  if (marks.fuse === "pass") return "The fuel-pump fuse was open. Replace it with the amp on the lid. If it blows again, find the short. The pump is not condemned.";
  if (marks.relay === "pass") return "The CCRM has power and it clicks, and the dark green/yellow output never went hot. Replace the CCRM. Do not drop the tank.";
  if (marks.relay === "fail" && marks["ccrm-out"] === "fail") {
    return "The relay is not closing, or the light blue/orange feed is dead. That is the fuse, the feed wire, the relay coil, or the PCM command. It is not the pump.";
  }
  if (marks["both-sides"] === "fail") return "Power is not getting through the inertia switch. Replace the switch if only the feed side goes hot. If neither side goes hot, go back to the CCRM output.";
  if (marks.hat === "fail" && marks["both-sides"] === "pass") {
    return "Power dies between the inertia switch and the tank connector. Repair that wire. The pump has not been proven bad.";
  }
  if (marks.ground === "fail") return "The pump ground is bad. Clean the eye near the tank and retest before you buy a pump.";
  if (marks.ground === "pass" && marks.hat === "pass") {
    return "Battery voltage at the pump, ground drop is clean, and it does not run. The pump is the failed part. Drop the tank and replace the sock with it.";
  }
  if (marks.prime === "pass" && !marks.hat) {
    return "The pump does prime. If the car still will not start, leave this circuit and check spark and rail pressure. A pump that only fails hot still needs a gauge, not a guess.";
  }
  return null;
}

// lib/mustang/store.ts
var WALK_KEY = "mustang.walkthrough.v1";
function loadWalk() {
  try {
    const o = JSON.parse(localStorage.getItem(WALK_KEY) || "null");
    const flow = o && o.v === 1 ? flowById(o.flowId) : void 0;
    if (!flow) return {};
    const marks = {};
    if (o.marks && typeof o.marks === "object") {
      for (const [id, mark] of Object.entries(o.marks)) {
        if (mark === "pass" || mark === "fail") marks[id] = mark;
      }
    }
    const step = Math.min(flow.steps.length - 1, Math.max(0, Math.floor(Number(o.step) || 0)));
    return { flowId: flow.id, step, marks, reading: String(o.reading ?? "").slice(0, 400) };
  } catch {
    return {};
  }
}
function saveWalk(s) {
  try {
    localStorage.setItem(WALK_KEY, JSON.stringify({ v: 1, flowId: s.flowId, step: s.step, marks: s.marks, reading: s.reading }));
  } catch {
  }
}
function framePart(id) {
  const part = PARTS[id];
  const stage = Math.max(live.targetStage, part?.stage ?? 0);
  live.targetStage = stage;
  live.focusId = id;
  live.focusing = true;
  live.dolly = null;
}
var useMustang = create((set, get) => ({
  selected: null,
  hover: null,
  trace: [],
  mode: "both",
  trans: "t5",
  paintHex: "#8f1d22",
  paintAlpha: 1,
  paintGrad: false,
  paintTo: "#1a1a1e",
  bgHex: "#141413",
  bgAlpha: 1,
  bgGrad: false,
  bgTo: "#3a2a28",
  zoomDrives: true,
  system: "all",
  section: null,
  circuit: "all",
  query: "",
  focusTick: 0,
  hidden: {},
  menu: null,
  dock: "walk",
  railOpen: false,
  pin: null,
  railW: 340,
  carShare: 0.72,
  flowId: null,
  step: 0,
  marks: {},
  reading: "",
  ...loadWalk(),
  select: (id, frame = false) => {
    const mode = get().mode;
    const nextMode = id && frame && mode === "sheet" ? "both" : id && !frame && mode === "car" ? "both" : mode;
    set({
      selected: id,
      trace: traceOf(id),
      mode: nextMode,
      query: id ? "" : get().query
    });
    if (id && frame) {
      framePart(id);
      set({ focusTick: get().focusTick + 1 });
    }
  },
  setHover: (id) => set({ hover: id }),
  setMode: (mode) => set({ mode }),
  setTrans: (trans) => {
    const selected = get().selected;
    let next = selected;
    if (trans === "4r70w" && (selected === "clutch" || selected === "flywheel")) next = "torque-converter";
    if (trans === "t5" && selected === "torque-converter") next = "clutch";
    set({ trans, selected: next, trace: traceOf(next) });
  },
  setPaintHex: (paintHex) => set({ paintHex }),
  setPaintAlpha: (paintAlpha) => set({ paintAlpha: Math.min(1, Math.max(0, paintAlpha)) }),
  setPaintGrad: (paintGrad) => set({ paintGrad }),
  setPaintTo: (paintTo) => set({ paintTo }),
  setBgHex: (bgHex) => set({ bgHex }),
  setBgAlpha: (bgAlpha) => set({ bgAlpha: Math.min(1, Math.max(0, bgAlpha)) }),
  setBgGrad: (bgGrad) => set({ bgGrad }),
  setBgTo: (bgTo) => set({ bgTo }),
  setZoomDrives: (zoomDrives) => set({ zoomDrives }),
  setSystem: (system) => set({ system }),
  setSection: (section) => set({ section }),
  setCircuit: (circuit) => set({ circuit }),
  setQuery: (query) => set({ query }),
  setStage: (stage) => {
    live.targetStage = stage;
    live.focusing = false;
    live.focusId = null;
    live.recenter = true;
    live.dolly = null;
  },
  hide: (id) => set({ hidden: { ...get().hidden, [id]: true }, menu: null }),
  showHidden: () => set({ hidden: {}, menu: null }),
  openMenu: (id, x, y) => set({ menu: { id, x, y } }),
  closeMenu: () => set({ menu: null }),
  showOnCar: () => {
    const id = get().selected;
    if (get().mode === "sheet") set({ mode: "both" });
    if (!id) return;
    framePart(id);
    set({ focusTick: get().focusTick + 1 });
  },
  showOnSheet: () => {
    if (get().mode === "car") set({ mode: "both" });
    set({ dock: "sheet" });
  },
  setDock: (dock) => set({ dock, mode: get().mode === "car" ? "both" : get().mode }),
  setRailOpen: (railOpen) => set({ railOpen }),
  setPin: (pin) => set({ pin }),
  setRailW: (railW) => set({ railW: Math.min(520, Math.max(260, railW)) }),
  setCarShare: (carShare) => set({ carShare: Math.min(0.86, Math.max(0.42, carShare)) }),
  startFlow: (id) => {
    const flow = flowById(id) ?? flowForPart(id);
    const partId = flow.steps[0]?.partId ?? null;
    set({
      flowId: flow.id,
      step: 0,
      marks: {},
      reading: "",
      dock: "walk",
      mode: get().mode === "car" ? "both" : get().mode,
      circuit: flow.circuit,
      selected: partId,
      trace: traceOf(partId)
    });
    saveWalk(get());
  },
  setStep: (step) => {
    const flow = flowById(get().flowId);
    if (!flow) return;
    const next = Math.min(flow.steps.length - 1, Math.max(0, step));
    const partId = flow.steps[next]?.partId ?? null;
    set({ step: next, selected: partId, trace: traceOf(partId) });
    saveWalk(get());
    if (partId) framePart(partId);
  },
  markStep: (stepId, mark) => {
    const flow = flowById(get().flowId);
    const marks = { ...get().marks, [stepId]: mark };
    set({ marks });
    saveWalk(get());
    if (!flow) return;
    const index = flow.steps.findIndex((step) => step.id === stepId);
    if (mark === "pass" && index >= 0 && index < flow.steps.length - 1) {
      const partId = flow.steps[index + 1].partId;
      set({ step: index + 1, selected: partId, trace: traceOf(partId) });
      saveWalk(get());
      framePart(partId);
    }
  },
  setReading: (reading) => {
    set({ reading });
    saveWalk(get());
  },
  clearWalk: () => {
    set({ flowId: null, step: 0, marks: {}, reading: "" });
    try {
      localStorage.removeItem(WALK_KEY);
    } catch {
    }
  }
}));

// lib/mustang/types.ts
var UNVERIFIED = "not verified, see EVTM";
var PAINTS = [
  { id: "red", name: "Laser Red", hex: "#8f1d22" },
  { id: "black", name: "Black", hex: "#1a1a1e" },
  { id: "silver", name: "Silver", hex: "#c5c8ce" },
  { id: "white", name: "Oxford White", hex: "#e4e0d8" }
];
var STAGES = [
  { id: 0, name: "Whole", hint: "Car together" },
  { id: 1, name: "Body", hint: "Panels and lamps" },
  { id: 2, name: "Cabin", hint: "Interior and wheels" },
  { id: 3, name: "Drivetrain", hint: "Powertrain drops out" },
  { id: 4, name: "Engine", hint: "Covers and accessories" },
  { id: 5, name: "Internals", hint: "Rotating assembly" }
];
var SYSTEM_LABEL = {
  body: "Body",
  glass: "Glass",
  chassis: "Chassis",
  suspension: "Suspension",
  brake: "Brakes",
  engine: "Engine",
  driveline: "Driveline",
  exhaust: "Exhaust",
  cooling: "Cooling",
  fuel: "Fuel",
  interior: "Interior",
  electrical: "Electrical"
};
var CIRCUIT_LABEL = {
  power: "Charging",
  ground: "Grounds",
  start: "Start",
  ignition: "Ignition",
  fuel: "Fuel",
  sensor: "Sensors",
  lamps: "Lamps"
};
var CIRCUIT_COLOR = {
  power: "#a45a56",
  ground: "#8a8a90",
  start: "#b3a288",
  ignition: "#c2b6a4",
  fuel: "#7d8e78",
  sensor: "#8c98a3",
  lamps: "#a89880"
};

export {
  require_scheduler,
  require_react,
  NODES,
  WIRES,
  createStore,
  PARTS,
  partView,
  searchParts,
  flowById,
  flowForPart,
  verdict,
  live,
  openAmount,
  explodeOf,
  useMustang,
  UNVERIFIED,
  PAINTS,
  STAGES,
  SYSTEM_LABEL,
  CIRCUIT_LABEL,
  CIRCUIT_COLOR,
  require_jsx_runtime
};
/*! Bundled license information:

react/cjs/react.development.js:
  (**
   * @license React
   * react.development.js
   *
   * Copyright (c) Meta Platforms, Inc. and affiliates.
   *
   * This source code is licensed under the MIT license found in the
   * LICENSE file in the root directory of this source tree.
   *)

react/cjs/react-jsx-runtime.development.js:
  (**
   * @license React
   * react-jsx-runtime.development.js
   *
   * Copyright (c) Meta Platforms, Inc. and affiliates.
   *
   * This source code is licensed under the MIT license found in the
   * LICENSE file in the root directory of this source tree.
   *)

scheduler/cjs/scheduler.development.js:
  (**
   * @license React
   * scheduler.development.js
   *
   * Copyright (c) Meta Platforms, Inc. and affiliates.
   *
   * This source code is licensed under the MIT license found in the
   * LICENSE file in the root directory of this source tree.
   *)
*/
