---
title: "Good Tools Get Simpler Over Time"
subtitle: "— Being able to build something is not the same as needing to"
slug: good-tools-get-simpler
order: 3
date: "2026-08-31"
status: "published"
summary: "My elaborate first intervalometer broke, and the last one I built was simple enough to fit inside a battery box. Being able to build something is not the same as needing to — and why I decided not to automate certain things even though I could."
series: "Making My Own Tools"
series_part: 2
series_total: 2
source_slug: good-tools-get-simpler
related_links:
  - label: "What is Sidekick"
    url: "/en/sidekick"
---

Last time I wrote about how, if what I need does not exist, I build it.

I wrote software for computers.

At work I built measurement jigs.

And once I started photographing digitally, I ended up building external power supplies too.

Put that way, it might look as though I designed and built the optimal thing from the outset every time something was needed.

Of course that is not what happened.

If anything, the opposite.

The first version of a thing is usually a nuisance.

You build it because you need it.

You carry it out into the field.

You use it.

It breaks.

You find the parts that are inconvenient.

Times change and better components or products appear.

And so you build it again.

For the same purpose, I have built a number of different things.

Some of them ended up far simpler than the first one.

## The first intervalometer was quite elaborate

Once I started making long exposures of the stars, I needed to trigger the camera at fixed intervals, on and on.

These days cameras have built-in interval shooting, or you can control them from a smartphone.

Back then it was not so easy.

So I built my own release system.

The first one was a fairly elaborate circuit built with CMOS logic.

And it did not simply fire the shutter at a fixed interval.

Only the very first frame of the session was triggered by the camera body's own interval timer.

That was used as a trigger, after which an external circuit took over the releases.

Why go to all that trouble?

Because I was later renaming the files using the date and time down to the second — and the milliseconds as well.

If the start of a session reads

**18:00:00**

it feels good.

That is all it was.

And was the camera's own clock, which determined that 18:00:00, actually accurate?

On that point:

**close enough is fine.**

Even now I find it a strange thing to have cared about.

But for me, "how many milliseconds accurate is the clock" and "does the session start neatly on the zero second" were evidently two different questions.

Be fussy where it matters.

Do not worry about the parts that do not.

## It broke

That release system worked very well.

When I built it, I was still an employee at a company.

Companies have oscilloscopes.

I could build the circuit, look at the waveform, check the timing, and adjust it.

Later on, though, it broke — a little.

By then I had left the company and gone freelance.

Naturally, there was no oscilloscope to hand.

If I wanted to fix it, one option was to buy a cheap oscilloscope.

But I thought:

**Am I really going to buy an oscilloscope for this?**

It was not worth it.

In that case, better to build something simpler.

## In the end, it fit inside a battery box

After that I built several simplified releases, I think.

Along the way I came across an interesting component.

It was a three-terminal part originally intended for things like making an LED blink.

The oscillation frequency was fixed by the part number, and there were versions at 1 Hz, 2 Hz, 4 Hz, 8 Hz — something around there.

I no longer remember the exact part numbers or frequencies.

But looking at it I thought:

**"This will do."**

One battery.

One of those three-terminal parts.

And the wiring to the camera.

I may have added a resistor.

That was more or less all of it.

I do not remember making a proper circuit board either.

I stuffed the part and the wiring into the empty space in a battery box and fixed it in place with adhesive so it would not move.

Done.

It is incomparably simpler than the CMOS circuit I built first.

But the job it does is the same.

**Fire the camera's shutter at the interval you need.**

If it can do that, it is enough.

## Complicated is not the same as superior

Because I had been an engineer, I can build a complicated circuit when one is needed.

But complicated circuits bring complicated problems.

More components.

More places that can fail.

Adjustment becomes necessary.

Repairing it may require test equipment.

Whereas a battery and a three-terminal part have almost nothing in them that can break.

For a tool you carry out to a location, that is sometimes the better option.

Building something technically advanced and

**being a good tool are not the same thing.**

This was not something I understood from the start.

Build, use, break, build again.

It is something I came to understand gradually while doing that.

## If building it is a hassle, buy it

Of course I did not build everything myself every time.

When making my own was too much trouble, I also used Nikon's MC-36 release.

It is a release with a built-in interval timer.

I was not using it in the ordinary way, though.

To get around a camera-side limit that becomes a problem in long continuous sessions, I used it with a particular configuration.

Later, when I began teaching nightscape photography courses at Photo Advice, I shared that method as well.

What was interesting is that you did not even need to buy an actual MC-36.

There were Chinese-made compatible units.

The price was about a tenth of the original, as I recall.

And they were sold with connectors for Nikon and other manufacturers such as Canon.

In the course I introduced the compatible unit and the settings.

But one of the people who bought one apparently became unsure about the settings and contacted Nikon.

I heard that when they explained the settings I had taught and asked their question, they were not given much of a hearing.

Which is understandable.

It is probably not a use the manufacturer had in mind.

But:

**if it works, that is fine.**

There is no need to build one yourself.

## I wanted a specific connector. They wouldn't sell me one

Something similar happened back when I was building external power supplies.

Cameras had a socket for connecting an AC adapter.

The problem was that connector.

It was not a common DC plug but a proprietary part.

To get hold of one by normal means, you had to buy the original AC adapter and

**cut the cable off.**

That was the only way.

But buying an entire AC adapter for a single connector is terrible value.

I once asked someone at the manufacturer.

Might there be one lying around in-house — pulled from a repair, or a part due to be scrapped?

They looked for me.

Later they told me:

"We couldn't find one."

A shame.

But that is not a reason to be annoyed with the manufacturer.

If it isn't there, it isn't there.

So think of another way.

## The power supply changed many times too

The external power supply itself did not stay the same either.

First, radio-control battery packs.

Then eneloop cells.

For long sessions in the cold I wired them in series to reach the voltage I needed, and then those strings in parallel to gain capacity.

I once ran a setup for about fourteen hours in conditions close to minus thirty degrees Celsius.

Even with the cells frozen solid, it kept going.

But today there is no need to build anything like that.

There are USB-PD power banks.

There are trigger cables to pull out the voltage you need.

So use those.

There is no reason to defend a method I once struggled to build myself.

**If a new off-the-shelf product is easier, I switch to it.**

## The "air filter"

I approach lenses in much the same way.

As a rule I choose lenses that perform well.

For mountain photography in particular, that is not somewhere I want to compromise.

But I almost never use the hood that comes with a lens.

Hoods are bulky in the mountains.

They add weight.

So even when I buy a new lens, the hood goes back in the box.

I generally do not use protective filters either.

But I do want to protect the filter thread at the front of the lens.

If you knock it against a rock and deform it, you may not be able to fit a filter afterwards.

So sometimes I remove the glass from a protective filter and mount just the ring.

I call this, entirely on my own,

**an "air filter."**

Obviously it does nothing at all if a stone flies into the front element.

But in my experience in the mountains, the probability of a stone striking the front element directly is far lower than the probability of knocking the lens barrel against something.

In that case, the ring alone is enough.

And if the front element does get scratched?

I have it repaired, or if necessary buy the lens again.

I reckon that is cheaper than owning an expensive protective filter for every lens I have.

This is not a general claim that protective filters are unnecessary.

**Given how I work, that is the judgement I have made.**

That is all.

## If I'm not carrying a hood, I don't compromise on the lens

Of course, not using a hood can make ghosting and flare more likely.

Which is exactly why the performance of the lens itself matters.

When light does get in, I block it by hand.

Sometimes I carry a flat piece of something for the purpose.

But usually, when I need it, I do not have it with me.

So in the end I often shade the lens with my hand.

At the same time, I sometimes find a slightly quirky lens — a Chinese 50mm f/1.0, say — genuinely interesting.

That is

**because it's play.**

Having a high-performance lens and then using a quirky one for fun is enjoyable.

But if

**that is all you have,**

then for me it is a different matter.

High performance is not automatically right.

Cheap and interesting is not automatically right either.

What you need changes depending on what you are using it for.

## I once made all of Photoshop scriptable

I have gone through similar trial and error in software.

This was before Sidekick.

I once made Photoshop's main functions controllable from JSX.

Tone curves.

Saturation.

And the other functions needed for image processing, one after another, callable from a program.

What I wanted was automatic development.

Analyse the image.

Look at the result and decide:

"For this photograph, soften the contrast a little with a tone curve."

"Raise the saturation slightly."

Then choose the right function, set the right parameters, and process it automatically.

That is how far I wanted to go.

Driving Photoshop from a program, I got a long way.

But it stopped after that.

## I couldn't decide "what to do"

The problem was not Photoshop.

I could move a tone curve.

I could change saturation.

I could call whatever function was needed.

But:

**what should be done to this photograph?**

That was the part I could not get a computer to judge.

I think the limits of AI at the time were part of it.

In the end that system was never finished.

I started building it and stopped.

Looking back, I had once tried to solve, at that time, a problem I would later take up again in Sidekick Portrait.

That software did not evolve into Sidekick Portrait, though.

I tried it once, and stopped at the point of realizing that

**automating operations and automating judgement are entirely different things.**

That is all it was.

## I could automate it. But I don't

The reverse happens too.

I photograph waves.

There are parts of wave photography that could be automated.

Technically, it can be done.

So would it not be easier to automate it?

But I have not.

When I photograph waves, even though it may look like I am simply pressing the shutter, I am making fine adjustments on the spot.

Watch the wave with my own eyes.

Watch the next wave.

Adjust slightly depending on the state of it.

And repeat.

If I automated that, I would lose the ability to watch and adjust in real time.

That is not all.

Handing it to the camera also makes my own shooting less attentive.

And the hit rate drops as a result.

So:

**I could automate it, but I don't.**

## "Just let the computer do it" was not enough

Last time I wrote that when I was doing research in Professor Takagi's laboratory at the Institute of Industrial Science, University of Tokyo, in my fourth year, I heard him say something to the effect of:

**Anything that can be automated should be given to the computer. The human mind is there to do creative work.**

I still think that is fundamentally right.

There is no need for a person to stack thousands of images by hand for a lighten composite.

Let the computer do it.

Nor is there any need for a person to endlessly repeat, over thousands of frames, work a computer can handle.

But photographing waves taught me something as well.

**Not everything a person does is "drudgery that should be replaced by a computer."**

Even something that looks like simple repetition may involve looking, sensing, judging, and adjusting along the way.

Take that away too, and the photographs become dull.

## Clear every night is not the same night every night

The same is true of nightscape photography.

Take a new moon.

A place where the Milky Way is clearly visible.

A forecast of clear skies.

On paper, the conditions are perfect.

I once stayed several nights at Enzanso, photographing stars every night.

Utterly clear, every day.

And yet,

**the Milky Way looked different every night.**

How clear the air is.

How much water vapour there is.

There are conditions that "fine" in a forecast does not capture.

You can calculate that it is a new moon.

You can calculate where the Milky Way will be.

You know sunset and sunrise.

But that alone does not determine the photograph you get that night.

The calculation is not wrong.

**It is that some things can be known by calculation and some things can only be known on site.**

## Everyone with a nose for it went outside

This was during one of those stays at Enzanso.

That day we were inside cloud the whole time.

You could barely see the mountains.

Then, towards evening, the cloud began to break up a little.

I went out to shoot.

The manager of Enzanso went out too.

Photographers and cameramen —

**everyone with a nose for it went out to shoot.**

The cloud never cleared completely.

But now and then it opened, just for a moment.

And you could see towards Mt. Yari.

The evening sun struck it.

A sea of cloud spread from directly below Mt. Yari all the way to the foot of Mt. Tsubakuro, where I was standing.

The conditions were extraordinary.

After the sun went down, the manager of Enzanso came over.

"Where on earth were you shooting?"

I hadn't been nearby, he said.

And then:

"I've been here since I was a child, and I've never seen conditions like that."

With conditions that good, where exactly had Murata been shooting from?

I imagine the manager suspected

**that I had found a better spot than his and shot from there.**

I did shoot, of course.

I think I got it, and got it well.

Probably no worse than the manager did.

But we never compared.

So which of us did better, I do not know.

## In the end it comes down to where you stand

Same mountain.

Same hour.

Same evening light.

Same sea of cloud.

Even so,

**where you stand changes the photograph.**

Can that spot be determined entirely by calculation?

I do not think so.

I look at maps.

I look at the positions of the sun and moon.

I look at forecasts a great deal.

I think hard about everything that can be reasoned out.

But when a fellow photographer at a mountain hut asks me:

"Murata-san, may I shoot alongside you tomorrow morning?"

and I answer:

"Of course,"

and they ask:

"So where are we going?"

I sometimes answer:

**"I won't know until I wake up tomorrow and step outside."**

Do I turn right out of the hut, or left?

Even that I cannot know without looking outside.

Look at the cloud.

Look at the light.

Look at the air.

And in the end, sometimes I decide with

**"this way, somehow."**

## Don't build it. Don't automate it. Don't let it decide.

When I was younger, if what I needed did not exist, I built it.

I built complicated circuits.

I wrote software.

In time I understood that if something simpler will do, simpler is better.

And further, that

**there is no need to build everything you are capable of building.**

Nor to automate everything that can be automated.

And now I think that

**letting a computer calculate and letting a computer decide the photograph are different things.**

If a computer can do in one night the image processing that would take a person a month, let it.

If it can accurately calculate when and where a celestial object will be, let it calculate.

But:

Do you want to take that photograph.

Are you going there today.

Do you go right or left once you are on site.

Do you look at the light in front of you and abandon the photograph you had planned.

None of that needs to be decided for you by a computer.

A tool is not there to take photographs in place of a person.

**It only needs to take on the tedious parts so that a person can take photographs.**

Sidekick, which I am building now, is in the end that kind of tool too.

— To be continued
