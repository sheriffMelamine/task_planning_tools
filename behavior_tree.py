#!/usr/bin/env python
import time
import asyncio
import py_trees as pt  # type: ignore
from abc import ABC, abstractmethod


class ConditionBehavior(pt.behaviour.Behaviour):
    def __init__(self, name, condition_fn, *args, verbose=True, **kwargs):
        super().__init__(name)
        self.fn = condition_fn
        self.args = args
        self.kwargs = kwargs
        self.verbose = verbose

    def update(self):
        if self.fn(*self.args, **self.kwargs):
            if self.verbose:
                print(f"[BT] Condition OK -> SUCCESS ({self.name}).")
            return pt.common.Status.SUCCESS
        else:
            return pt.common.Status.RUNNING


class CommandBehavior(pt.behaviour.Behaviour):
    def __init__(
        self, name, command_queue, status_dict, command, *args, verbose=True, **kwargs
    ):
        super().__init__(name)
        self.command_queue = command_queue
        self.status_dict = status_dict  # 0 - Inactive, 1 - Running, 2 - Success
        self.command = command
        self.args = args
        self.kwargs = kwargs
        self.verbose = verbose

    def initialise(self):
        self.status_dict[self.name] = 0

    def update(self):
        if self.status_dict[self.name] == 0:
            self.command_queue.put_nowait(
                (self.name, self.command, self.args, self.kwargs)
            )
            self.status_dict[self.name] = 1
            if self.verbose:
                print(
                    f"[BT] Command sent -> {self.name}, args={self.args}, kwargs={self.kwargs}"
                )
            return pt.common.Status.RUNNING
        elif self.status_dict[self.name] == 2:
            if self.verbose:
                print(f"[BT] Command complete -> SUCCESS ({self.name})")
            return pt.common.Status.SUCCESS
        else:
            return pt.common.Status.RUNNING


class BehaviorTreePlan(ABC):
    def __init__(self):
        self.done = False
        self.command_queue = asyncio.Queue()
        self.status_dict = dict()
        self._set_tree()

    @abstractmethod
    def create_tree(self) -> pt.trees.BehaviourTree:
        """
        Define the Behavior Tree for the Robot.
        Use CommandBehavior and ConditionBehavior as nodes

        """
        pass

    def _set_tree(self):
        self.tree = self.create_tree()

    async def execute_tree(self, rest):
        while not self.done:
            if not self.command_queue.empty():
                cmd = await self.command_queue.get()
                key, action, args, kwargs = cmd
                await action(*args, **kwargs)
                self.status_dict[key] = 2
            await asyncio.sleep(rest)

    def tick_till_success(self):
        if not self.done:
            self.tree.tick()
            self.done = self.tree.root.status == pt.common.Status.SUCCESS

    def display_tree(self):
        print(pt.display.ascii_tree(self.tree.root))

    def is_done(self):
        return self.done


def are_all_trees_done(*trees: BehaviorTreePlan):
    return all(t.is_done() for t in trees)


def merged_loop(*trees: BehaviorTreePlan, rest=0.1):
    while not are_all_trees_done(*trees):
        for t in trees:
            t.tick_till_success()
        time.sleep(rest)


async def merged_loop_async(*trees: BehaviorTreePlan, rest=0.1):
    while not are_all_trees_done(*trees):
        for t in trees:
            t.tick_till_success()
        await asyncio.sleep(rest)
