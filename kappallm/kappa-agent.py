from litellm import completion
import kappy
from kappy.kappa_common import KappaError
import re
import textwrap

sys_prompt = """
You are a helpful AI assistant proficient in the use of Kappa, the rule-based language for modeling systems of interacting agents.
You task is to extract protein-protein interactions from a biological text into a Kappa program.
For instance, the text "A is a kinase able to phosphorylate B" translates into the Kappa program:
`
// Agent declaration
%agent: A(b) // b is the binding site for connecting A to B
%agent: B(a,s{u,p}) // a is the binding site for connecting B to A, s is a site that can be phosphorylated (p) or not (u)

// Rule declaration
'A.B' A(b[.]),B(a[.],s{u}) <-> A(b[1]),B(a[1],s{u}) @ 'k_AB_on','k_AB_off' //we assume A cannot bind B if it is already phosphorylated
'AphosB' A(b[1]),B(a[1],s{u}) ->  A(b[.]),B(a[.],s{p}) @ 'kphos'

// initial state
%init: 100 A(),B()

// defining constants (putting 1 if unkown)
'k_AB_on' 1
'k_AB_off' 1
'kphos' 1
`

First explain the interactions in plain English.
Then write the Kappa program that represents the model in a code block.

Ready?
"""

usr_prompt = """
Here is the model:
```
{bio_model}
```
"""


def parse(response: str) -> str:
    md_pattern = r"```(?:kappa)?(.*?)```"
    if match := re.search(md_pattern, response, re.DOTALL):
        return match.group(1).strip()
    raise KappaError(f"Could not parse {response}")


def validate(code: str):
    kappa_client = kappy.KappaStd()
    kappa_client.add_model_string(code)
    kappa_client.project_parse()


def one_shot(llm: str, prompt: str) -> str:
    resp = completion(
        model=llm,
        messages=[
            {"content": sys_prompt, "role": "system"},
            {"content": prompt, "role": "user"},
        ],
    )
    code = parse(resp.choices[0].message.content)  # type: ignore
    return code


def pass_at_k(llm: str, bio_model: str, k: int) -> str | None:
    for _ in range(k):
        prompt = usr_prompt.format(bio_model=bio_model)
        code = one_shot(llm, prompt)
        try:
            print(f"Trying:\n{textwrap.indent(code, '  ')}\n\n")
            validate(code)
            return code
        except KappaError as e:
            print(f"[Kappa Error]: {e.errors}")
    print(f"Could not find model after {k} iterations")


def multi_trials(llm: str, bio_model: str, k: int) -> str:
    trials = []
    for _ in range(k):
        prompt = usr_prompt.format(bio_model=bio_model)
        if trials:
            prompt += f"Here is a list of your unsuccesful previous attempts. DO NOT TRY ONE OF THIS SOLUTION AGAIN:"
            for t in trials:
                prompt += f"\n\n```kappa\n{t}\n```"
        code = one_shot(llm, prompt)
        try:
            print(f"Trying:\n{textwrap.indent(code, '  ')}\n\n")
            validate(code)
            return code
        except KappaError as e:
            print(f"[Kappa Error]: {e.errors}")
        trials.append(code)
    print(f"Could not find model after {k} iterations")


if __name__ == "__main__":
    # resp = pass_at_k(
    #     llm="ollama/qwen2.5-coder:7b-instruct", bio_model="A(x) -> A(x[1]) @ 1e-2", k=4
    # )
    resp = multi_trials(
        llm="ollama/qwen2.5-coder:7b-instruct", bio_model="A(x) -> A(x[1]) @ 1e-2", k=4
    )
    print(resp)
