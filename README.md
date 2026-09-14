# Request Manager library

[![Coverage](https://raw.githubusercontent.com/AgrospAI/request-manager/refs/heads/main/coverage.svg)](https://github.com/agrospai/request-manager)


Typed Python library to help with request lifecycle.

## Installation

```bash
uv add request-manager
```

### Optional Dependencies

You can also install the optional dependencies to make the different default client implementations work.

As of now, there is only one default client implementation using the httpx package. To use it, install `request-manager` with:

```bash
uv add "request-manager[httpx]"
```

## Core

The library consists of three core components, the `RequestManager`, the `Client`, and the `Runner`.

The `RequestManager` provides a way to assign the different `fetch` and `expect` callbacks and is responsible for the orchestration of the execution.

The `Client` is the one in charge of translating the domain-specific HTTP models into implementation specific requests and responses.

The `Runner` is the one in charge of executing the different callbacks.

## Usage

To make use of the library, the simplest form is using the default `httpx` client implementation.

```python
from request_manager import RequestManager, Request
from request_manager.clients.httpx import HttpxClient

manager = RequestManager.create(
    client=HttpxClient.default(),
)

@manager.fetch()
def todos() -> Request:
    return Request(
        method="GET",
        path="/todos"
    )

manager.run()
```

Running the sample code will make the created request using python's `httpx` package in the case the following configuration is.

### Configuration

Using the default `HttpxClient` implementation needs the following configuration object.

```python
class HttpxClientConfig(BaseModel):
    base_url: Annotated[
        str,
        Field(default="", description="Base URL used for the requests"),
    ]

    authorization_header: Annotated[
        str,
        Field(description="API authorization header to use", default="Authorization"),
    ]

    authorization_scheme: Annotated[
        str,
        Field(description="API authorization scheme to use", default="Bearer"),
    ]

    api_key: Annotated[
        str | None,
        Field(description="API key to use", default=None),
    ]

    timeout: Annotated[
        float,
        Field(description="Maximum timeout for reponse arrival", default=5.0),
    ]
```

The default implementation, which we use via the `HttpxClient.default()` also uses this configuration object, but it gets automatically loaded from:

- Environment variables (prefixed with `RM__`)
- `CLI` arguments

If both are defined, the `CLI` arguments override the loaded environment variables. If unsure, you can run the simple `todos` script shown earlier (or just a simple `manager.run()`) with the `--help` flag as in:

```bash
$ uv run ./scripts/test.py --help
usage: request-manager [-h] [--base-url BASE_URL] [--authorization-header AUTHORIZATION_HEADER] [--authorization-scheme AUTHORIZATION_SCHEME] [--api-key API_KEY]
                       [--timeout TIMEOUT]

Test different API endpoints, capturing results and forwarding them

options:
  -h, --help            show this help message and exit
  --base-url BASE_URL   Base URL used for the requests(Env. RM__BASE_URL)
  --authorization-header AUTHORIZATION_HEADER
                        API authorization header to use(Env. RM__AUTHORIZATION_HEADER)
  --authorization-scheme AUTHORIZATION_SCHEME
                        API authorization scheme to use(Env. RM__AUTHORIZATION_SCHEME)
  --api-key API_KEY     API key to use(Env. RM__API_KEY)
  --timeout TIMEOUT     Maximum timeout for reponse arrival(Env. RM__TIMEOUT)
```

## Advanced Usage

### CLI Arguments

With the capability of loading values from environment variables and arguments, we also provide a way for end-users to define extra arguments in case they need them in the definition of requests, like in the following example.

```python
from typing import Annotated

from dotenv import load_dotenv
from pydantic import BaseModel, Field
from request_manager import Request, RequestManager, RequestOptions
from request_manager.httpx.client import HttpxClient

load_dotenv()

class Arguments(BaseModel):
    poll_timeout: Annotated[
        int,
        Field(
            default=300,
            description="Seconds before unsuccessful response timeout (default: 300)",
        ),
    ]

    poll_interval: Annotated[
        int,
        Field(default=5, description="Seconds between polling attempts (default: 5)"),
    ]

manager = RequestManager.create(
    arguments=Arguments,
    client=HttpxClient.default(),
)

@manager.fetch()
def poll_todos() -> Request:
    return Request(
        method="GET",
        path="/todos/",
        options=RequestOptions(
            timeout=manager.arguments.poll_timeout,
            retry_backoff=manager.arguments.poll_interval,
        ),
    )

manager.run()
```

In this case, the `Arguments` will get instantiated and validated with values from environment variables or `CLI`, and will be available to use via `manager.arguments`. In this example, we also added `RequestOptions`, which enables the end-user to configure the request runtime with configurations for:

- Timeout (`timeout: float [default=0]`). Maximum seconds to wait for a successful response.
- Retries (`retries: int [default=1]`). Maximum amount of retries upon an unsuccessful response.
- Retry Backoff (`retry_backoff: float [default=0.2]`). Seconds to wait before retrying the defined request.
- Is Success? (`is_sucess: Callable[[Response[bytes]], bool] | None [default=None]`). Custom function to check if a response is succesfull. By default, a response is successful if its HTTP status code does not correspond to an error code.

Also, running the script with the `-h` or `--help` flag, will prompt the end-user with the following helping message:

```bash
$ uv run ./scripts/test.py -h
usage: request-manager [-h] [--base-url BASE_URL] [--authorization-header AUTHORIZATION_HEADER] [--authorization-scheme AUTHORIZATION_SCHEME]
                       [--api-key API_KEY] [--timeout TIMEOUT] [--poll-timeout POLL_TIMEOUT] [--poll-interval POLL_INTERVAL]

Test different API endpoints, capturing results and forwarding them

options:
  -h, --help            show this help message and exit
  --base-url BASE_URL   Base URL used for the requests(Env. RM__BASE_URL)
  --authorization-header AUTHORIZATION_HEADER
                        API authorization header to use(Env. RM__AUTHORIZATION_HEADER)
  --authorization-scheme AUTHORIZATION_SCHEME
                        API authorization scheme to use(Env. RM__AUTHORIZATION_SCHEME)
  --api-key API_KEY     API key to use(Env. RM__API_KEY)
  --timeout TIMEOUT     Maximum timeout for reponse arrival(Env. RM__TIMEOUT)
  --poll-timeout POLL_TIMEOUT
                        Seconds before unsuccessful response timeout (default: 300)(Env. RM__POLL_TIMEOUT)
  --poll-interval POLL_INTERVAL
                        Seconds between polling attempts (default: 5)(Env. RM__POLL_INTERVAL)
```

### Request dependency and response validation

As we commented earlier, we load and validate values from environment variables and `CLI` arguments. Apart from that, we can also validate the given responses.

For example, we can make assertions on the responses as in the following example, or use previous results as part of a request.

```python
from pydantic import BaseModel
from request_manager import Request, RequestManager, RequestOptions
from request_manager.httpx.client import HttpxClient

manager = RequestManager.create(
    arguments=Arguments,
    client=HttpxClient.default(),
)

class Todo(BaseModel):
    id: int

class TodosResponse(BaseModel):
    prev: str | None
    next: str | None
    results: list[Todo]

@manager.fetch()
def fetch_todos() -> Request:
    return Request(method="GET", path="/todos/")

@manager.expect(fetch_todos, type_=TodosResponse)
def assert_result(response: Response[TodosResponse]) -> None:
    print(f"Received {len(response.results)} todos!")
    if response.next is None:
        # This is an example, could also be done by defining TodosResponse as:
        #
        # class TodosResponse(BaseModel):
        #     next: str # non-optional string
        #     ...

        raise manager.error("Response did not contain a next page URL")

@manager.expect(depends_on=fetch_todos, type_=TodosResponse)
def fetch_next_todos(response: Response[TodosResponse]) -> Request:
    return Request(
        method="GET",
        url=response.next, # This will ignore the configured base URL
    )

manager.run()
```

In this example, the manager will first make the `fetch_todos` request, validate the response content with the `TodosResponse pydantic.BaseModel`, assert that its result contains a `next` value, and then fetch the `next` todos page with `fetch_next_todos`.
