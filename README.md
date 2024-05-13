# ortelius-ms-scorecard

![Release](https://img.shields.io/github/v/release/ortelius/ms-scorecard?sort=semver)
![license](https://img.shields.io/github/license/ortelius/.github)

![Build](https://img.shields.io/github/actions/workflow/status/ortelius/ms-scorecard/build-push-chart.yml)
[![MegaLinter](https://github.com/ortelius/ms-scorecard/workflows/MegaLinter/badge.svg?branch=main)](https://github.com/ortelius/ms-scorecard/actions?query=workflow%3AMegaLinter+branch%3Amain)
![CodeQL](https://github.com/ortelius/ms-scorecard/workflows/CodeQL/badge.svg)
[![OpenSSF
-Scorecard](https://api.securityscorecards.dev/projects/github.com/ortelius/ms-scorecard/badge)](https://api.securityscorecards.dev/projects/github.com/ortelius/ms-scorecard)

![Discord](https://img.shields.io/discord/722468819091849316)

> Version 0.1.0

ortelius-ms-scorecard

## Path Table

| Method | Path | Description |
| --- | --- | --- |
| GET | [/health](#gethealth) | Health |
| GET | [/msapi/scorecard](#getmsapiscorecard) | Get Scorecard |

## Reference Table

| Name | Path | Description |
| --- | --- | --- |
| HTTPValidationError | [#/components/schemas/HTTPValidationError](#componentsschemashttpvalidationerror) |  |
| ScoreCard | [#/components/schemas/ScoreCard](#componentsschemasscorecard) |  |
| StatusMsg | [#/components/schemas/StatusMsg](#componentsschemasstatusmsg) |  |
| ValidationError | [#/components/schemas/ValidationError](#componentsschemasvalidationerror) |  |

## Path Details

***

### [GET]/health

- Summary  
Health

- Description  
This health check end point used by Kubernetes

#### Responses

- 200 Successful Response

`application/json`

```ts
{
  status?: string
  service_name?: string
}
```

***

### [GET]/msapi/scorecard

- Summary  
Get Scorecard

#### Parameters(Query)

```ts
frequency?: Partial(string) & Partial(null)
```

```ts
environment?: Partial(string) & Partial(null)
```

```ts
lag?: Partial(string) & Partial(null)
```

```ts
appname?: Partial(string) & Partial(null)
```

```ts
appid?: Partial(string) & Partial(null)
```

#### Responses

- 200 Successful Response

`application/json`

```ts
{
  domain?: string
[]
[]
}
```

- 422 Validation Error

`application/json`

```ts
{
  detail: {
    loc?: Partial(string) & Partial(integer)[]
    msg: string
    type: string
  }[]
}
```

## References

### #/components/schemas/HTTPValidationError

```ts
{
  detail: {
    loc?: Partial(string) & Partial(integer)[]
    msg: string
    type: string
  }[]
}
```

### #/components/schemas/ScoreCard

```ts
{
  domain?: string
[]
[]
}
```

### #/components/schemas/StatusMsg

```ts
{
  status?: string
  service_name?: string
}
```

### #/components/schemas/ValidationError

```ts
{
  loc?: Partial(string) & Partial(integer)[]
  msg: string
  type: string
}
```
