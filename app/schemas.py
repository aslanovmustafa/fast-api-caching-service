from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

InputString = Annotated[
    str,
    StringConstraints(strict=True, max_length=1000),
]

class PayloadCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    list_1: list[InputString] = Field(max_length=1000)
    list_2: list[InputString] = Field(max_length=1000)

    @model_validator(mode="after")
    def check_length(self) -> "PayloadCreate":
        if len(self.list_1) != len(self.list_2):
            raise ValueError("The length of list_1 and list_2 must be equal")
        return self

class PayloadContent(BaseModel):
    output: str