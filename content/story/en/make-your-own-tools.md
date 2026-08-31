---
title: "If the Tool You Need Doesn't Exist, Build It"
subtitle: "— I was making strange things long before I became a photographer"
slug: make-your-own-tools
order: 2
date: "2026-08-31"
status: "published"
summary: "From a PC-8001mkII and cassette tapes to university research, measurement jigs in my engineering job, and external power supplies for digital cameras. A look back at a habit I have had for a long time: if the tool I need isn't sold anywhere, I build it."
series: "Making My Own Tools"
series_part: 1
series_total: 2
source_slug: make-your-own-tools
related_links:
  - label: "What is Sidekick"
    url: "/en/sidekick"
---

"What do you do when the tool you need isn't for sale?"

These days you would search Amazon first. If it isn't there, you look on Google. If it still isn't there, you might go as far as overseas sites.

And if you still cannot find it, you give up.

That is probably the normal order of things.

In my case it seems to have been a little different, and it has been that way for a long time.

If something on the market will do the job, use it.

If something made for another purpose will do the job, that is fine too.

And if neither works, build it.

It is not that I was consciously following a principle from the start.

Looking back, though, that is what I have been doing all along.

## The PC-8001mkII and cassette tapes

When I was a university student I used an NEC PC-8001mkII.

Computers back then were nothing like today's.

You even used cassette tape to store data.

There was an official cassette recorder for it, and the catalogue said — as you would expect — that it was optimized for use with the computer.

I did not use it.

I was something of an audio enthusiast at the time, so there was a much better cassette deck at home.

"This will do, won't it?"

I connected an ordinary audio cassette deck, not a computer one, and used that.

It caused me no trouble at all. Not once.

Digital recording was much the same story.

Before DAT arrived, one way to record music digitally was to combine a PCM processor with a VTR.

I liked audio, but I also liked anime.

I used a Sony F11 VTR to make digital recordings.

For the time, that was not an especially unusual way to do it.

But thinking about it now, it is a strange thing.

**In order to record music digitally, I was writing it down as a video signal.**

If it got the job done, what the machine was originally for did not matter much.

## The first software I wrote was probably a word processor

I wrote programs on the PC-8001mkII too.

What was the first one?

It was more than forty years ago, so I no longer remember clearly.

I think it was probably something like a word processor.

I was not trying to produce impressive documents.

**I wanted to make track lists for my cassette tapes.**

That was all.

There were commercial word processors, I am sure. But they were probably too expensive to buy just for what I wanted to do.

As I remember it, I got hold of two or three cheap pieces of software and put together what I needed while referring to how each of them worked.

After that I made something like a database for managing music tracks.

And something like a lookup table for a board game.

I was not trying to master programming as such.

**There was a result I wanted, and I wrote programs to get it.**

I think it started around then.

## "Murata's is completely different from everyone else's"

At Tokai University's School of Marine Science and Technology — in my third year, I think — I took lectures from Professor Hajime Fukushima.

It was a programming class, and the language was FORTRAN, as I recall.

At one point we were given an assignment:

"Write a program and bring it in."

I thought it through myself, wrote a program, and handed it in.

Later, Professor Fukushima said something to me about that program.

It was more than forty years ago so these are not his exact words, but the gist was this:

"It was bizarre code. When I first looked at it, I couldn't believe it would run at all. I'd never seen code like it. But it does run, and when you look closely the logic holds up. The other students — I don't know whether they showed each other their work or not — all write in more or less the same way. Murata's is completely different. At the very least, there's no doubt that Murata worked all of it out himself."

I am still not sure whether that was praise.

But Professor Fukushima

**did not treat "different from everyone else" as a mistake in itself.**

Does it actually run?

Does the logic hold together?

That, I think, is what he was looking at.

As a child in Japan, I was often scolded with:

"Why can't you do it the same way as everyone else?"

When my father was posted to New York and I lived in the United States from fifth grade through first year of junior high, I had the opposite experience.

One of the local kids once asked me:

"Ichiro, what do you do on Saturdays?"

I answered with something like "the same as everyone else."

And he said:

"That can't be right."

In his family, they went to church together on Sundays. But a Japanese family would be different. So what he was asking was what my family actually did.

**"The same as everyone else" was not an answer.**

I learned that such a world existed too.

I am not going to claim that these experiences made me who I became.

But looking back, I may always have cared less about "how is this normally done" and more about

**"does this actually work?"**

## To the Institute of Industrial Science, University of Tokyo

Around the time I became a fourth-year student, I ended up doing research in Professor Mikio Takagi's laboratory at the Institute of Industrial Science, University of Tokyo.

I was sent there from Tokai University as something like an external research student, as I remember.

Why me? I still do not really know.

It was certainly not because I was selected for outstanding grades.

When Professor Fukushima told me about it, I remember him checking:

"Come to think of it, Murata — you haven't failed any required courses, have you? Are your grades all right?"

That does not sound much like a question from someone who had scrutinized my transcript beforehand.

What I worked on in the Takagi laboratory was tracking the movement of surface water masses using NOAA satellite imagery.

And there is something Professor Takagi said that I still remember.

Not a precise quotation, but the sense of it was:

**Anything that can be automated should be given to the computer. The human mind is there to do creative work. It is not there to do drudgery.**

The research itself also pointed in that direction — how to get a computer to do processing that people had been doing by hand.

To say that those words determined the rest of my life would make the story too neat.

I have not walked through life thinking about them.

But now, forty years later, when I line up the things I have built,

"I have done a fair amount of exactly that,"

is what I find myself thinking.

## "If you can't measure it, build something that can"

After university I went to work in circuit design.

The work covered mixed analogue and digital LSI, from planning through design, bring-up, and volume production.

At one point I was responsible for circuitry involved in television sync signals.

You design the circuit and simulate it.

So far, so good.

The problem is the circuit once it actually exists.

Where does the signal appear relative to the master clock?

Within a span of about one sixtieth of a second, I wanted to confirm positions to the microsecond.

But what you have on the bench is an oscilloscope.

Looking at the waveform tells you:

"Probably around here."

What I wanted to know was not "probably."

Nor was it a problem that buying an expensive instrument would solve. At least at the time, I could not find anything that would make the measurement I needed as it was.

So:

**If you can't measure it, build something that can.**

Feed in a reference clock and a reset signal from outside, and follow the timing with counters.

I built a dedicated measurement jig.

It took about a month, I think.

Work happened to be relatively quiet, and my manager understood what I was doing.

With it, things I could previously only call "probably correct" could be confirmed as numbers.

That job had nothing whatsoever to do with photography.

But thinking about it now, the idea that

**if you cannot measure it, create a state in which you can**

does not feel much different from how I still work.

## I built it with 3 bits, and was told to make it 2

In my company years I also had the opposite experience.

I was designing a circuit that controlled an IC over I²C-BUS.

Three functions had to be assigned.

They were separate functions, so I designed it using three bits.

At the design review, though, I was told:

"There's no point using three bits. Two bits gives you four combinations, so make it two."

I thought three bits was better, but there was nothing to be done.

I changed it to two.

In due course the IC was completed and a release meeting was held.

At which someone further up the chain became angry:

"Why is this two bits? Why didn't you make it three?"

The person who had demanded the change to two bits spent hours explaining.

Partway through, he looked to me for rescue.

But all I could say was:

**"I did say we should use three bits from the start, didn't I?"**

Meeting the specification and being a natural design are not necessarily the same thing.

This was not something I only understood later — I understood it perfectly well at the time. But a company is not something you build on your own.

That is how it goes.

## I started shooting photographs digitally

In time I began photographing with digital cameras.

This was the era of the Nikon D1.

Early digital SLRs had problems that are hard to imagine now.

One of them was the battery.

Winter mountains were especially hard.

In bad conditions, a fully charged original battery could become unusable after only a few frames.

And original batteries were not cheap.

At the time, professionals using the D1 had worked out tricks such as using the battery's casing and terminals to draw power from an external pack.

I built one too.

At first I used things like radio-control battery packs.

Later I built a supply from eneloop cells in series, and then those strings in parallel.

Much later still, I moved to USB-PD power banks and trigger cables.

The batteries changed.

The cameras changed.

But what I was doing stayed the same.

**If the camera won't keep running for as long as I want to shoot, make it run.**

That is all.

A photographer friend who had bought a D1 once told me:

"I bought the same D1 as you. And you were right about the battery."

Later I built one of my external supplies and gave it to him.

He was pleased with it.

Something I built because I was stuck also solved someone else's problem.

Come to think of it, I had experiences like that from around this time too.

## Of course, I break things too

Written this way, it may look as though everything I built went well.

It did not.

Much later, I built an external power supply for a mid-range LUMIX.

I did not modify the body itself.

It worked by modifying the battery side to accept power from outside.

And there:

**I got plus and minus the wrong way round.**

It took an instant.

A camera I had only just bought was dead.

"Ah…"

is presumably what I thought.

But also:

**Well, these things happen.**

If you build things yourself, sometimes you fail.

There are probably a good many programs I started and never finished.

As for code I wrote that turned out to be useless, there is no end of it.

Tools break out in the field, too.

And as times change, an approach that once made sense stops being worth it.

When that happens, you build it again.

## I assumed nobody would buy Tsubame

In the 2000s I started writing software for photography as well.

Tsubame, and then Kita-Tsubame.

These were not programs only for my own use; I released them as paid shareware.

But at first I assumed

**nobody would buy them.**

It was software written by some person nobody had heard of.

And at the time, nowhere near as many people were using digital cameras as today.

Unexpectedly, though, people did buy them.

And then the emails come.

"This part is awkward to use…"

I see.

Something that works fine for me turns out to have problems when someone else uses it.

What I could fix, I fixed.

Building something for yourself and building something for other people are different.

That obvious fact was also something I started to experience around then.

## Building tools is not the point

Lining up all these old stories, I may look like someone who has always just enjoyed making things.

I see it a little differently.

If I do not have to build something, there is no need to build it.

If something on the market will do, buy it.

If something made for another purpose can be repurposed, that is fine too.

If none of that achieves the goal, build it.

And having built something once is no reason to cling to it.

If it breaks, repair it.

If repairing it is not worth the effort, build something simpler.

If the times change, switch to a different method.

What mattered to me, I think, was

**not "what did you use," but "can you take the photograph with it."**

And there is one more thing that becomes clear further down this road.

**Being able to build something does not mean you should.**

**Being able to automate something does not mean you should automate it.**

It took me a little longer to notice that.

— To be continued
